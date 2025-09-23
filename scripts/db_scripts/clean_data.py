"""
OpChat Database Data Cleaning Script

Deletes all data from the database while preserving the schema structure.
Tables remain intact with all columns, constraints, and indexes.

Usage:
    python scripts/db_scripts/clean_data.py
    make clean_db
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import models after path setup
try:
    from app.models import Chat, DirectMessage, GroupChat, Membership, Message, User
except ImportError as e:
    print(f"Error importing models: {e}")
    print(
        "Make sure you're running from the project root and models are properly defined"
    )
    sys.exit(1)

# Database connection
APP_DATABASE_URL = (
    os.getenv("APP_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql://opchat:opchat@postgres:5432/opchat"
)

engine = create_engine(APP_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def clean_database_data():
    """Delete all data from database tables in correct dependency order."""
    print("Cleaning database data...")

    session = SessionLocal()
    try:
        # Delete in reverse dependency order to avoid foreign key violations
        tables_cleaned = []

        # Messages (references chat and user)
        message_count = session.query(Message).count()
        if message_count > 0:
            session.query(Message).delete(synchronize_session=False)
            tables_cleaned.append(f"Messages: {message_count:,}")

        # Memberships (references chat and user)
        membership_count = session.query(Membership).count()
        if membership_count > 0:
            session.query(Membership).delete(synchronize_session=False)
            tables_cleaned.append(f"Memberships: {membership_count:,}")

        # Child chat tables (inherit from chat)
        group_count = session.query(GroupChat).count()
        if group_count > 0:
            session.query(GroupChat).delete(synchronize_session=False)
            tables_cleaned.append(f"Group Chats: {group_count:,}")

        dm_count = session.query(DirectMessage).count()
        if dm_count > 0:
            session.query(DirectMessage).delete(synchronize_session=False)
            tables_cleaned.append(f"Direct Messages: {dm_count:,}")

        # Base chat table
        chat_count = session.query(Chat).count()
        if chat_count > 0:
            session.query(Chat).delete(synchronize_session=False)
            tables_cleaned.append(f"Chats: {chat_count:,}")

        # Users (referenced by messages and memberships)
        user_count = session.query(User).count()
        if user_count > 0:
            session.query(User).delete(synchronize_session=False)
            tables_cleaned.append(f"Users: {user_count:,}")

        # Commit all deletions
        session.commit()

        if tables_cleaned:
            print("Data deleted:")
            for table_info in tables_cleaned:
                print(f"  - {table_info}")
            print("Database cleaned successfully!")
        else:
            print("Database was already empty.")

    except Exception as e:
        print(f"Error during database cleaning: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """Main cleaning function."""
    print("Starting OpChat database data cleaning...")

    try:
        clean_database_data()
        print("\nDatabase data cleaning completed successfully!")
        print("Schema structure (tables, columns, constraints) preserved.")

    except Exception as e:
        print(f"Database cleaning failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
