"""
Database Setup Script for OpChat

This script sets up the database with proper roles and permissions:
1. Creates migration role (DDL permissions)
2. Creates application role (data-only permissions)
3. Grants appropriate permissions

Usage:
    python scripts/db_scripts/setup_roles.py
    make setup_db_roles
"""

import os
import sys

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("Error: SQLAlchemy not installed. Please install it first:")
    print("pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# Constants
APP_NAME = "opchat"
MIGRATION_ROLE = f"{APP_NAME}_migration"
APP_ROLE = f"{APP_NAME}_app"
DEFAULT_MIGRATION_PASSWORD = "opchat_migration_pass"
DEFAULT_APP_PASSWORD = "opchat_app_pass"
DEFAULT_ADMIN_URL = "postgresql://opchat:opchat@postgres:5432/opchat"
DEFAULT_PORT = "5432"
EXPECTED_ROLE_COUNT = 2
TEST_TABLE_NAME = "test_migration_table"


def get_migration_password():
    """Get migration role password from environment."""
    return os.getenv("MIGRATION_DB_PASSWORD", DEFAULT_MIGRATION_PASSWORD)


def get_app_password():
    """Get app role password from environment."""
    return os.getenv("APP_DB_PASSWORD", DEFAULT_APP_PASSWORD)


def get_admin_database_url():
    """Get admin database URL from environment."""
    return os.getenv("ADMIN_DATABASE_URL", DEFAULT_ADMIN_URL)


def parse_database_url(database_url):
    """Parse database URL into components."""
    if "://" not in database_url:
        raise ValueError("Invalid DATABASE_URL format")

    url_parts = database_url.split("://")[1]

    if "@" not in url_parts:
        raise ValueError("Invalid DATABASE_URL format")

    auth, host_db = url_parts.split("@")
    user, password = auth.split(":")

    if ":" in host_db:
        host, port_db = host_db.split(":")
        port, database = port_db.split("/")
    else:
        host = host_db.split("/")[0]
        port = DEFAULT_PORT
        database = host_db.split("/")[1]

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def get_database_config():
    """Get database configuration from environment variables."""
    database_url = get_admin_database_url()
    return parse_database_url(database_url)


def role_exists(conn, role_name):
    """Check if a role exists."""
    result = conn.execute(
        text("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :role_name"),
        {"role_name": role_name},
    )
    return result.fetchone() is not None


def create_single_role(conn, role_name, password):
    """Create a single database role."""
    if role_exists(conn, role_name):
        print(f"  Role '{role_name}' already exists, skipping creation")
    else:
        print(f"  Creating role: {role_name}")
        conn.execute(
            text(f"CREATE ROLE {role_name} WITH LOGIN PASSWORD :password"),
            {"password": password},
        )


def create_roles(engine, config):
    """Create migration and application roles."""
    print("Creating database roles...")

    with engine.connect() as conn:
        trans = conn.begin()

        try:
            create_single_role(conn, MIGRATION_ROLE, get_migration_password())
            create_single_role(conn, APP_ROLE, get_app_password())

            trans.commit()
            print("  Roles created successfully!")

        except Exception as e:
            trans.rollback()
            print(f"  Error creating roles: {e}")
            raise


def grant_connection_permissions(conn, database):
    """Grant database connection permissions to roles."""
    conn.execute(text(f"GRANT CONNECT ON DATABASE {database} TO {MIGRATION_ROLE}"))
    conn.execute(text(f"GRANT CONNECT ON DATABASE {database} TO {APP_ROLE}"))


def grant_schema_permissions(conn):
    """Grant schema usage permissions to roles."""
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {MIGRATION_ROLE}"))
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))


def grant_migration_permissions(conn):
    """Grant DDL permissions to migration role."""
    conn.execute(text(f"GRANT CREATE ON SCHEMA public TO {MIGRATION_ROLE}"))
    conn.execute(
        text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {MIGRATION_ROLE}")
    )
    conn.execute(
        text(
            f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {MIGRATION_ROLE}"
        )
    )


def grant_default_privileges(conn):
    """Set up default privileges for future objects."""
    # Tables
    conn.execute(
        text(
            f"""
        ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATION_ROLE} IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}
    """
        )
    )

    # Sequences
    conn.execute(
        text(
            f"""
        ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATION_ROLE} IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}
    """
        )
    )


def grant_app_permissions(conn):
    """Grant data-only permissions to app role."""
    conn.execute(
        text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
        )
    )
    conn.execute(
        text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    )


def grant_role_membership(conn):
    """Grant app role membership to migration role."""
    conn.execute(text(f"GRANT {APP_ROLE} TO {MIGRATION_ROLE}"))


def setup_permissions(engine, config):
    """Set up permissions for roles."""
    print("Setting up permissions...")

    with engine.connect() as conn:
        trans = conn.begin()

        try:
            database = config["database"]

            grant_connection_permissions(conn, database)
            grant_schema_permissions(conn)
            grant_migration_permissions(conn)
            grant_default_privileges(conn)
            grant_app_permissions(conn)
            grant_role_membership(conn)

            trans.commit()
            print("  Permissions set up successfully!")

        except Exception as e:
            trans.rollback()
            print(f"  Error setting up permissions: {e}")
            raise


def verify_roles_exist(engine):
    """Verify that both roles exist with correct basic privileges."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
            SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
            FROM pg_catalog.pg_roles
            WHERE rolname IN (:migration_role, :app_role)
            ORDER BY rolname
        """
            ),
            {"migration_role": MIGRATION_ROLE, "app_role": APP_ROLE},
        )

        roles = result.fetchall()

        if len(roles) != EXPECTED_ROLE_COUNT:
            raise Exception(f"Expected {EXPECTED_ROLE_COUNT} roles, found {len(roles)}")

        for role in roles:
            rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin = role

            if not rolcanlogin:
                raise Exception(f"Role {rolname} cannot login")

            if rolsuper or rolcreaterole or rolcreatedb:
                raise Exception(f"Role {rolname} has excessive privileges")

        print("  Basic role properties: OK")


def test_migration_role_connection(config):
    """Test connection as migration role."""
    migration_url = f"postgresql://{MIGRATION_ROLE}:{get_migration_password()}@{config['host']}:{config['port']}/{config['database']}"
    migration_engine = create_engine(migration_url)

    with migration_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("  Migration role connection: OK")


def test_app_role_connection(config):
    """Test connection as app role."""
    app_url = f"postgresql://{APP_ROLE}:{get_app_password()}@{config['host']}:{config['port']}/{config['database']}"
    app_engine = create_engine(app_url)

    with app_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("  App role connection: OK")


def test_migration_role_ddl(config):
    """Test DDL operations for migration role."""
    migration_url = f"postgresql://{MIGRATION_ROLE}:{get_migration_password()}@{config['host']}:{config['port']}/{config['database']}"
    migration_engine = create_engine(migration_url)

    with migration_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Test CREATE TABLE
            conn.execute(
                text(
                    f"CREATE TABLE {TEST_TABLE_NAME} (id SERIAL PRIMARY KEY, name TEXT)"
                )
            )

            # Test INSERT
            conn.execute(text(f"INSERT INTO {TEST_TABLE_NAME} (name) VALUES ('test')"))

            # Test SELECT
            result = conn.execute(text(f"SELECT COUNT(*) FROM {TEST_TABLE_NAME}"))
            count = result.scalar()

            if count != 1:
                raise Exception(f"Expected 1 row, got {count}")

            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"Migration role DDL test failed: {e}") from e

    print("  Migration role DDL operations: OK")


def test_app_role_dml(config):
    """Test DML operations for app role."""
    app_url = f"postgresql://{APP_ROLE}:{get_app_password()}@{config['host']}:{config['port']}/{config['database']}"
    app_engine = create_engine(app_url)

    with app_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Test SELECT
            result = conn.execute(text(f"SELECT COUNT(*) FROM {TEST_TABLE_NAME}"))
            result.scalar()  # Just verify the query works, don't need the count

            # Test INSERT
            conn.execute(
                text(f"INSERT INTO {TEST_TABLE_NAME} (name) VALUES ('app_test')")
            )

            # Test UPDATE
            conn.execute(
                text(
                    f"UPDATE {TEST_TABLE_NAME} SET name = 'updated' WHERE name = 'app_test'"
                )
            )

            # Test DELETE
            conn.execute(text(f"DELETE FROM {TEST_TABLE_NAME} WHERE name = 'updated'"))

            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"App role DML test failed: {e}") from e

    print("  App role DML operations: OK")


def test_app_role_ddl_restriction(config):
    """Test that app role cannot perform DDL operations."""
    app_url = f"postgresql://{APP_ROLE}:{get_app_password()}@{config['host']}:{config['port']}/{config['database']}"
    app_engine = create_engine(app_url)

    with app_engine.connect() as conn:
        try:
            conn.execute(text("CREATE TABLE should_fail (id INTEGER)"))
            raise Exception("App role should not be able to create tables")
        except Exception as e:
            if "permission denied" not in str(e).lower():
                raise Exception(f"Unexpected error: {e}") from e

    print("  App role DDL restrictions: OK")


def test_default_privileges(config):
    """Test default privileges on new objects."""
    migration_url = f"postgresql://{MIGRATION_ROLE}:{get_migration_password()}@{config['host']}:{config['port']}/{config['database']}"
    migration_engine = create_engine(migration_url)

    # Create new table as migration role
    with migration_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(
                text(
                    "CREATE TABLE default_priv_test (id SERIAL PRIMARY KEY, data TEXT)"
                )
            )
            conn.execute(text("INSERT INTO default_priv_test (data) VALUES ('test')"))
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"Failed to create test table: {e}") from e

    # Test app role can access the new table
    app_url = f"postgresql://{APP_ROLE}:{get_app_password()}@{config['host']}:{config['port']}/{config['database']}"
    app_engine = create_engine(app_url)

    with app_engine.connect() as conn:
        trans = conn.begin()
        try:
            result = conn.execute(text("SELECT COUNT(*) FROM default_priv_test"))
            count = result.scalar()

            if count != 1:
                raise Exception(f"Expected 1 row, got {count}")

            conn.execute(
                text("INSERT INTO default_priv_test (data) VALUES ('app_data')")
            )
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"App role cannot access new table: {e}") from e

    # Clean up
    with migration_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DROP TABLE default_priv_test"))
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"Failed to clean up test table: {e}") from e

    print("  Default privileges: OK")


def cleanup_test_table(config):
    """Clean up test table created during verification."""
    migration_url = f"postgresql://{MIGRATION_ROLE}:{get_migration_password()}@{config['host']}:{config['port']}/{config['database']}"
    migration_engine = create_engine(migration_url)

    with migration_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text(f"DROP TABLE IF EXISTS {TEST_TABLE_NAME}"))
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise Exception(f"Failed to clean up test table: {e}") from e


def verify_roles(engine, config):
    """Verify that roles were created with correct permissions."""
    print("Verifying roles...")

    try:
        verify_roles_exist(engine)
        test_migration_role_connection(config)
        test_app_role_connection(config)
        test_migration_role_ddl(config)
        test_app_role_dml(config)
        test_app_role_ddl_restriction(config)
        test_default_privileges(config)
        cleanup_test_table(config)

        print("  Role verification completed successfully!")

    except Exception:
        # Attempt cleanup on failure
        try:
            cleanup_test_table(config)
        except Exception:
            pass  # Cleanup failure is not critical
        raise


def print_connection_strings(config):
    """Print database connection strings for the new roles."""
    migration_password = get_migration_password()
    app_password = get_app_password()

    print("\nEnvironment Variables:")
    print(
        f"   DATABASE_URL=postgresql://{MIGRATION_ROLE}:{migration_password}@{config['host']}:{config['port']}/{config['database']}"
    )
    print(
        f"   APP_DATABASE_URL=postgresql://{APP_ROLE}:{app_password}@{config['host']}:{config['port']}/{config['database']}"
    )


def print_setup_header():
    """Print setup header message."""
    print("Setting up OpChat database roles and permissions...\n")


def print_database_info(config, version_info):
    """Print database connection information."""
    print(
        f"Connecting to database: {config['database']} on {config['host']}:{config['port']}"
    )
    print(f"  Connected to PostgreSQL: {version_info}\n")


def print_success_message():
    """Print success completion message."""
    print("\nDatabase setup completed successfully!")


def test_database_connection(engine):
    """Test database connection and return version info."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.scalar()
        return version.split(",")[0]


def main():
    """Main setup function."""
    print_setup_header()

    try:
        config = get_database_config()

        # Create engine with admin privileges
        admin_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
        engine = create_engine(admin_url)

        # Test connection and get version
        version_info = test_database_connection(engine)
        print_database_info(config, version_info)

        # Set up roles and permissions
        create_roles(engine, config)
        setup_permissions(engine, config)
        verify_roles(engine, config)

        # Print connection information
        print_connection_strings(config)
        print_success_message()

    except Exception as e:
        print(f"Database setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
