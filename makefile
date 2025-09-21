.PHONY: run stop clean restart help lint ci-lint test ci-test security ci-security logs

# Default target
help:
	@echo "OpChat Backend - Available commands:"
	@echo "  run     - Start all services (API, WS Gateway, Postgres, Redis, RabbitMQ)"
	@echo "  stop    - Stop all services"
	@echo "  restart - Full restart (stop + clean + run) - REQUIRES CONFIRMATION"
	@echo "  clean   - Stop and remove volumes (WARNING: deletes all data) - REQUIRES CONFIRMATION"
	@echo "  logs    - Show logs from all services"
	@echo "  lint    - Run pre-commit hooks (formats code)"
	@echo "  ci-lint - Run linters in check mode (CI safe)"
	@echo "  test    - Run tests in Docker"
	@echo "  ci-test - Run tests directly (CI safe)"
	@echo "  security - Run security checks locally"
	@echo "  ci-security - Run security checks (CI safe)"

# Start all services (API, WS Gateway, Postgres, Redis, RabbitMQ) in detached mode
run:
	docker compose up -d --build
	@echo "Services starting... Check status with 'make logs'"

# Stop all running services
stop:
	docker compose down

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

# Show logs from all services
logs:
	docker compose logs -f

# Run pre-commit hooks (check mode - doesn't modify files)
lint:
	python -m pre_commit run --all-files

# Run linters in fix mode (modifies files)
lint-fix:
	ruff check . --fix
	black .
	isort .
	mypy .

# Run linters in check mode (CI safe)
ci-lint:
	ruff check .
	black --check .
	isort --check-only .
	mypy .

# Run tests inside Docker container (full environment)
test:
	docker compose exec api pytest

# Run tests directly without Docker (faster for CI)
ci-test:
	pytest

# Run security checks locally (requires dev dependencies)
security:
	pip-audit --format=json --output=pip-audit-report.json || true
	@echo "Security check completed. Check pip-audit-report.json for details."

# Run security checks in CI mode (assumes tools are already installed)
ci-security:
	pip-audit --format=json --output=pip-audit-report.json || true