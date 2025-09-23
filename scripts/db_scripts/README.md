# Database Scripts

This directory contains all database-related scripts for OpChat. These scripts handle role management, data population, verification, and performance testing.

## Overview

The database scripts are designed to work with the `system` container in `docker-compose.yaml`, which provides a dedicated environment for database operations and tooling.

## Scripts

### 1. setup_roles.py

Creates and configures database roles with proper permissions for security and separation of concerns.

**Purpose:** Sets up two database roles for OpChat:
- **`opchat_migration`** - DDL permissions for schema changes (used by Alembic)
- **`opchat_app`** - Data-only permissions for application runtime

**Usage:**
```bash
make setup_db_roles
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/setup_roles.py
```

**Features:**
- Idempotent (safe to run multiple times)
- Comprehensive permission verification
- Tests both DDL and DML capabilities
- Follows principle of least privilege

**Environment Variables:**
```bash
# Admin connection (for creating roles)
ADMIN_DATABASE_URL=postgresql://opchat:opchat@postgres:5432/opchat

# Migration role connection
DATABASE_URL=postgresql://opchat_migration:opchat_migration_pass@postgres:5432/opchat

# Application role connection
APP_DATABASE_URL=postgresql://opchat_app:opchat_app_pass@postgres:5432/opchat
```

### 2. populate.py

Creates small-scale, deterministic test data for development and testing.

**Purpose:** Populates the database with a predictable, minimal dataset:
- 5 users (alice, bob, charlie, diana, eve)
- 4 chats (2 direct messages, 2 group chats)
- 16 messages with realistic timestamps
- 10 memberships

**Usage:**
```bash
make populate
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/populate.py
```

**Features:**
- Deterministic UUIDs (same data every time)
- Realistic conversation patterns
- Constraint verification
- Uses data from `data/users.json` and `data/conversations.json`

### 3. populate_large.py

Creates large-scale, realistic test data for performance testing and load simulation.

**Purpose:** Generates substantial dataset for benchmarking:
- 200 users with realistic names
- 75 group chats with varied membership
- 300 direct message conversations
- ~25,000 messages over 4 months
- Realistic activity patterns (business hours weighting)

**Usage:**
```bash
make populate_large
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/populate_large.py
```

**Features:**
- Realistic temporal distribution
- Business hours activity weighting
- Varied message lengths and content
- Batch processing for performance
- Progress reporting during execution

### 4. verify_population.py

Verifies data integrity and constraint enforcement after population.

**Purpose:** Comprehensive data validation including:
- Row counts and basic statistics
- Sample data display
- Constraint verification (uniqueness, foreign keys)
- Data quality checks
- Format validation (DM keys, etc.)

**Usage:**
```bash
make verify_population
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/verify_population.py
```

**Features:**
- Comprehensive constraint checking
- Data quality validation
- Clear pass/fail reporting
- Sample data visualization
- Timeline and structure analysis

### 5. clean_data.py

Removes all data from database tables while preserving schema structure.

**Purpose:** Clean slate for fresh data population:
- Deletes all data in dependency order
- Preserves table structure and constraints
- Safe for development environment resets

**Usage:**
```bash
make clean_db
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/clean_data.py
```

**Features:**
- Confirmation prompt for safety
- Dependency-aware deletion order
- Preserves schema structure
- Reports deletion counts

### 6. benchmark.py

Runs comprehensive database performance benchmarks.

**Purpose:** Performance testing for critical database operations:
- Message timeline queries (pagination)
- User search and lookup operations
- Chat membership queries
- Complex join operations
- Index effectiveness validation

**Usage:**
```bash
make bench
# or directly:
docker compose exec system python3 /app/scripts/db_scripts/benchmark.py
```

**Features:**
- Multiple iterations for statistical accuracy
- Index performance validation
- Query timing analysis (avg/min/max)
- Performance threshold checking
- Comprehensive query coverage

**Performance Expectations:**
- Message timeline queries: <10ms
- User lookups: <5ms
- Membership queries: <10ms

## Data Files

### data/users.json
Defines the 5 deterministic users for `populate.py`:
- Consistent usernames and attributes
- Predictable for testing scenarios
- Password: `password123` for all users

### data/conversations.json
Defines the conversation structure for `populate.py`:
- 2 direct message conversations
- 2 group chats with topics
- 16 messages with realistic content and timing

## Makefile Integration

All scripts are integrated into the main `makefile` for easy execution:

### Individual Commands
```bash
make setup_db_roles    # Create database roles
make migrate           # Run Alembic migrations
make populate          # Small-scale data population
make populate_large    # Large-scale data population
make verify_population # Verify data integrity
make clean_db          # Clean all data (with confirmation)
make bench            # Run performance benchmarks
```

### Automated Workflows
```bash
make db_setup          # Complete setup: roles + migrations + population
make db_hard_reset     # Nuclear option: delete everything
make db_reset_and_setup # Full reset + complete setup
```

## Development Workflow

### Fresh Setup
```bash
make db_setup          # Sets up roles, runs migrations, populates data
```

### Reset Environment
```bash
make clean_db          # Clean data only
make populate          # Repopulate with fresh data
```

### Performance Testing
```bash
make populate_large    # Generate large dataset
make bench            # Run benchmarks
```

### Complete Reset
```bash
make db_reset_and_setup # Nuclear reset + full setup
```

## Security Considerations

### Development Environment
- Simple passwords for ease of development
- All credentials visible in docker-compose.yaml
- Suitable for local development only

### Production Environment
- Change all passwords to secure, randomly generated values
- Use proper secret management
- Consider connection pooling and SSL requirements
- Review and adjust role permissions as needed

## Troubleshooting

### Common Issues

**Permission Denied:**
```bash
# Ensure system container has execute permissions
docker compose exec system chmod +x /app/scripts/db_scripts/*.py
```

**Connection Errors:**
```bash
# Verify database is running
docker compose ps postgres

# Check environment variables
docker compose exec system env | grep DATABASE_URL
```

**Role Creation Failures:**
```bash
# Ensure you're using admin credentials
# Check ADMIN_DATABASE_URL environment variable
```

### Database State Issues

**Constraint Violations:**
- Use `make clean_db` to clear existing data
- Ensure proper deletion order in cleanup scripts

**Migration Conflicts:**
- Use `make db_hard_reset` for complete schema reset
- Verify Alembic revision history

## Architecture Notes

### Role Separation
- **Migration Role:** Can create/modify tables, run DDL
- **App Role:** Can only read/write data, no schema changes
- **Admin Role:** Full privileges for setup operations

### Container Strategy
- **System Container:** Dedicated environment for DB operations
- **API Container:** Application runtime only
- **Separation of Concerns:** Clear boundaries between operational and runtime environments

### Data Strategy
- **Small Population:** Deterministic, reproducible test data
- **Large Population:** Realistic scale for performance testing
- **Verification:** Comprehensive data integrity checking
- **Benchmarking:** Performance validation and regression testing