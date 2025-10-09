# OpChat Backend Makefile
# Available commands organized by category

.PHONY: help run stop clean restart logs lint lint-fix lint-all ci-lint test ci-test security ci-security setup-tests-env run-tests run-tests-dir teardown-tests-env setup-db-roles migrate populate populate-large verify-population test-population bench-population clean-db db-hard-reset db-setup db-reset-and-setup bench

# Default target
help:
	@echo "OpChat Backend - Available commands:"
	@echo ""
	@echo "Docker Operations:"
	@echo "  run             - Start all services (API, WS Gateway, Postgres, Redis, RabbitMQ)"
	@echo "  stop            - Stop all services"
	@echo "  restart         - Full restart (stop + clean + run) - REQUIRES CONFIRMATION"
	@echo "  clean           - Stop and remove volumes (WARNING: deletes all data) - REQUIRES CONFIRMATION"
	@echo "  logs            - Show logs from all services"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint            - Run pre-commit hooks (check mode)"
	@echo "  lint-fix        - Run linters in fix mode (modifies files)"
	@echo "  ci-lint         - Run linters in check mode (CI safe)"
	@echo "  security        - Run security checks locally"
	@echo "  ci-security     - Run security checks (CI safe)"
	@echo ""
	@echo "Testing:"
	@echo "  setup-tests-env   - Setup test database containers"
	@echo "  run-tests         - Run pytest tests (requires setup-tests-env)"
	@echo "  run-tests-dir DIR - Run tests for specific directory (e.g., make run-tests-dir tests/api)"
	@echo "  teardown-tests-env - Shutdown test database containers"
	@echo "  test              - Run tests in Docker"
	@echo "  ci-test           - Run tests directly (CI safe)"
	@echo ""
	@echo "Database Operations:"
	@echo "  setup-db-roles    - Create database roles (migration and app)"
	@echo "  migrate           - Run database migrations"
	@echo "  populate          - Populate database with small test data (5 users, 16 messages)"
	@echo "  populate-large    - Populate database with large test data (200+ users, 25k+ messages)"
	@echo "  verify-population - Verify database population integrity"
	@echo "  test-population   - Small population test (populate + verify-population)"
	@echo "  bench-population  - Large population test (populate-large + verify-population)"
	@echo "  clean-db          - Delete all data from database (requires confirmation)"
	@echo "  bench             - Run database performance benchmarks"
	@echo ""
	@echo "Database Automation:"
	@echo "  db-hard-reset     - Hard reset: delete tables, volumes, everything (requires confirmation)"
	@echo "  db-setup          - Full setup: roles + migrations + small population (requires confirmation)"
	@echo "  db-reset-and-setup - Complete reset and setup (hard reset + full setup) (requires confirmation)"

# =============================================================================
# DOCKER OPERATIONS
# =============================================================================

# Start all services in detached mode
run:
	docker compose up -d --build
	@echo "Services starting... Check status with 'make logs'"

# Stop all running services
stop:
	docker compose down

# Show logs from all services
logs:
	docker compose logs -f

# Full restart (stop + clean + run) - REQUIRES CONFIRMATION
restart:
	@echo "WARNING: This will delete ALL data and restart everything!"
	@echo "This includes:"
	@echo "  - All database data"
	@echo "  - All Redis data"
	@echo "  - All RabbitMQ data"
	@echo "  - All Docker volumes"
	@echo ""
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	@echo "Stopping services..."
	docker compose down -v
	@echo "Cleaning up volumes..."
	docker system prune -f
	@echo "Starting services..."
	docker compose up -d --build
	@echo "Full restart complete! Check status with 'make logs'"

# Stop services and remove all volumes (WARNING: deletes all data) - REQUIRES CONFIRMATION
clean:
	@echo "WARNING: This will delete ALL data!"
	@echo "This includes:"
	@echo "  - All database data"
	@echo "  - All Redis data"
	@echo "  - All RabbitMQ data"
	@echo "  - All Docker volumes"
	@echo ""
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	@echo "Stopping services and removing volumes..."
	docker compose down -v
	docker system prune -f
	@echo "All data removed. Run 'make run' to start fresh."

# =============================================================================
# CODE QUALITY
# =============================================================================

# Run pre-commit hooks (check mode - doesn't modify files)
lint:
	python -m pre_commit run --all-files

# Run linting tools directly on ALL files (including untracked)
lint-all:
	@echo "Running Black on all Python files..."
	black --check --diff .
	@echo "Running Ruff on all Python files..."
	ruff check .
	@echo "Running isort on all Python files..."
	isort --check-only --diff .
	@echo "Running MyPy on all Python files..."
	mypy . --ignore-missing-imports

# Run linters in fix mode (modifies files)
lint-fix:
	ruff check . --fix
	black .
	isort .
	mypy .

# Run linters in check mode (CI safe)
ci-lint:
	ruff check . --exclude alembic --exclude migrations --exclude tests
	black --check . --exclude "(alembic|migrations|tests)"
	isort --check-only . --skip-glob "alembic/*" --skip-glob "migrations/*" --skip-glob "tests/*"
	mypy . --show-error-codes --exclude alembic --exclude migrations --exclude tests

# Run security checks locally (requires dev dependencies)
security:
	pip-audit --format=json --output=pip-audit-report.json || true
	@echo "Security check completed. Check pip-audit-report.json for details."

# Run security checks in CI mode (assumes tools are already installed)
ci-security:
	pip-audit --format=json --output=pip-audit-report.json || true

# =============================================================================
# TESTING
# =============================================================================

# Setup test database containers
setup-tests-env:
	@echo "Setting up test environment..."
	docker-compose -f docker-compose.test.yml up -d --build
	@echo "Waiting for test database to be ready..."
	@sleep 5
	@for i in $$(seq 1 20); do \
		if docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U opchat_test_user -d opchat_test -c "SELECT 1;" >/dev/null 2>&1; then \
			echo "Database is ready after $$i attempts"; \
			break; \
		fi; \
		if [ $$i -eq 20 ]; then \
			echo "ERROR: Database failed to become ready after 20 attempts (40 seconds)"; \
			docker-compose -f docker-compose.test.yml logs postgres-test; \
			exit 1; \
		fi; \
		echo "Attempt $$i/20 - waiting..."; \
		sleep 2; \
	done
	@echo "Test environment is ready!"
	@echo "Test database URL: postgresql://opchat_test_user:test_password@localhost:5433/opchat_test"

# Run pytest tests (requires setup-tests-env)
run-tests:
	@echo "Running tests..."
	@if ! docker-compose -f docker-compose.test.yml ps test-runner | grep -q "Up"; then \
		echo "ERROR: Test environment is not running. Please run 'make setup-tests-env' first."; \
		exit 1; \
	fi
	@echo "Running all tests in container..."
	docker-compose -f docker-compose.test.yml exec test-runner python -m pytest tests/ -v --tb=short

# Run tests for specific directory (requires setup-tests-env)
# Usage: make run-tests-dir tests/api
run-tests-dir:
	@if [ -z "$(DIR)" ]; then \
		echo "ERROR: Please specify a directory. Usage: make run-tests-dir DIR=tests/api"; \
		echo "Available test directories:"; \
		echo "  tests/api          - API endpoint tests"; \
		echo "  tests/services     - Service layer tests"; \
		echo "  tests/repositories - Repository layer tests"; \
		echo "  tests/integration  - Integration tests"; \
		echo "  tests/core         - Core functionality tests"; \
		echo "  tests/auth         - Authentication tests"; \
		exit 1; \
	fi
	@echo "Running tests for directory: $(DIR)"
	@if ! docker-compose -f docker-compose.test.yml ps test-runner | grep -q "Up"; then \
		echo "ERROR: Test environment is not running. Please run 'make setup-tests-env' first."; \
		exit 1; \
	fi
	@if [ ! -d "$(DIR)" ]; then \
		echo "ERROR: Directory '$(DIR)' does not exist."; \
		exit 1; \
	fi
	@echo "Running tests in $(DIR)..."
	docker-compose -f docker-compose.test.yml exec test-runner python -m pytest $(DIR)/ -v --tb=short

# Shutdown test database containers
teardown-tests-env:
	@echo "Shutting down test environment..."
	docker-compose -f docker-compose.test.yml down
	@echo "Test environment shut down!"

# Run tests inside Docker container (full environment)
test:
	docker compose exec api pytest

# Run tests directly without Docker (faster for CI)
ci-test:
	pytest

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

# Create database roles with proper permissions
setup-db-roles:
	@echo "Setting up database roles..."
	docker compose exec system python3 /app/scripts/db_scripts/setup_roles.py

# Run database migrations
migrate:
	@echo "Running database migrations..."
	docker compose exec api alembic upgrade head

# Populate database with small test dataset
populate:
	@echo "Populating database with test data..."
	docker compose exec system python3 /app/scripts/db_scripts/populate.py

# Populate database with large-scale test dataset
populate-large:
	@echo "Populating database with large-scale test data..."
	@echo "This will create 200+ users, 375+ chats, and 25,000+ messages"
	docker compose exec system python3 /app/scripts/db_scripts/populate_large.py

# Verify database population integrity
verify-population:
	@echo "Verifying database population..."
	docker compose exec system python3 /app/scripts/db_scripts/verify_population.py

# Run small population test (populate + verify)
test-population: populate verify-population
	@echo "Population test completed successfully!"

# Run large population test (populate_large + verify)
bench-population: populate-large verify-population
	@echo "Large-scale population and verification completed!"

# Delete all data from database (requires confirmation)
clean-db:
	@echo "WARNING: This will delete ALL data from the database (tables will remain)!"
	@echo "This action cannot be undone."
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	docker compose exec system python3 /app/scripts/db_scripts/clean_data.py

# =============================================================================
# DATABASE AUTOMATION
# =============================================================================

# Hard reset: delete everything (tables, volumes, containers)
db-hard-reset:
	@echo "WARNING: This will perform a HARD RESET of the database!"
	@echo "This will delete:"
	@echo "  - All database tables and schema"
	@echo "  - All database volumes and data"
	@echo "  - All database containers"
	@echo "  - Database roles and permissions"
	@echo ""
	@echo "This action cannot be undone."
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	@echo "Stopping database services..."
	docker compose stop postgres
	@echo "Removing database containers and volumes..."
	docker compose rm -f postgres
	docker volume rm opchat-backend_postgres_data 2>/dev/null || true
	@echo "Database hard reset completed!"

# Full database setup: roles + migrations + population
db-setup:
	@echo "WARNING: This will set up the complete database environment!"
	@echo "This will:"
	@echo "  - Create database roles and permissions"
	@echo "  - Run database migrations"
	@echo "  - Populate database with test data (overwrites existing data)"
	@echo ""
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	@echo "Setting up complete database environment..."
	@echo "Step 1/4: Creating database roles..."
	$(MAKE) setup-db-roles
	@echo "Step 2/4: Running database migrations..."
	$(MAKE) migrate
	@echo "Step 3/4: Populating database with test data..."
	$(MAKE) populate
	@echo "Step 4/4: Verifying database population..."
	$(MAKE) verify-population
	@echo "Database setup completed successfully!"

# Complete reset and setup (hard reset + full setup)
db-reset-and-setup:
	@echo "Performing complete database reset and setup..."
	@echo "This will:"
	@echo "  1. Hard reset the database (delete everything)"
	@echo "  2. Restart database services"
	@echo "  3. Set up roles and permissions"
	@echo "  4. Run migrations"
	@echo "  5. Populate with test data"
	@echo ""
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || (echo "Operation cancelled." && exit 1)
	@echo "Phase 1: Hard reset..."
	$(MAKE) db-hard-reset
	@echo "Phase 2: Restarting database services..."
	docker compose up -d postgres
	@echo "Waiting for database to be ready..."
	@sleep 10
	@echo "Phase 3: Full setup..."
	$(MAKE) db-setup
	@echo "Complete database reset and setup finished!"

# Run database performance benchmarks
bench:
	@echo "Running database performance benchmarks..."
	docker compose exec system python3 /app/scripts/db_scripts/benchmark.py