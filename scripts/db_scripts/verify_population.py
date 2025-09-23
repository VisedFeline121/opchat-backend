"""
OpChat Database Population Verification Script

Verifies that the population script created data correctly and all constraints are working.
"""

import os
import sys
from pathlib import Path

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("Error: SQLAlchemy not installed. Please install it first:")
    print("pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Constants
DEFAULT_DATABASE_URL = "postgresql://opchat:opchat@postgres:5432/opchat"
SEPARATOR_LINE = "=" * 50
MAX_SAMPLE_USERS = 5
MAX_SAMPLE_MESSAGES = 10
MAX_SAMPLE_CHATS = 4

# Table definitions for row counting
TABLES_TO_COUNT = [
    ("user", "Users"),
    ("chat", "Base Chats"),
    ("direct_message", "Direct Messages"),
    ("group_chat", "Group Chats"),
    ("membership", "Memberships"),
    ("message", "Messages"),
]


def get_database_url():
    """Get database URL from environment variables."""
    return os.getenv("APP_DATABASE_URL") or os.getenv(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )


def print_header():
    """Print verification header."""
    print("OpChat Database Population Verification")
    print(SEPARATOR_LINE)


def print_row_counts(conn):
    """Print row counts for all tables."""
    print("\nRow Counts:")
    total_records = 0

    for table, display_name in TABLES_TO_COUNT:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        count = result.scalar()
        print(f"  {display_name:15}: {count:,}")
        total_records += count

    print(f"  {'Total Records':15}: {total_records:,}")


def print_sample_users(conn):
    """Print sample user data."""
    print("\nUsers:")
    result = conn.execute(
        text(
            f'SELECT username, status, created_at FROM "user" ORDER BY created_at LIMIT {MAX_SAMPLE_USERS}'
        )
    )

    for row in result:
        print(f"  - {row[0]} ({row[1]}) - created: {row[2]}")


def print_chat_structure(conn):
    """Print chat structure overview."""
    print("\nChat Structure:")

    # Direct messages
    dm_result = conn.execute(
        text(
            """
        SELECT dm.dm_key, COUNT(m.id) as member_count, COUNT(msg.id) as message_count
        FROM direct_message dm
        LEFT JOIN membership m ON dm.id = m.chat_id
        LEFT JOIN message msg ON dm.id = msg.chat_id
        GROUP BY dm.id, dm.dm_key
        ORDER BY dm.dm_key
    """
        )
    )

    for row in dm_result:
        print(f"  DM: {row[0]} ({row[1]} members, {row[2]} messages)")

    # Group chats
    group_result = conn.execute(
        text(
            """
        SELECT gc.topic, COUNT(m.id) as member_count, COUNT(msg.id) as message_count
        FROM group_chat gc
        LEFT JOIN membership m ON gc.id = m.chat_id
        LEFT JOIN message msg ON gc.id = msg.chat_id
        GROUP BY gc.id, gc.topic
        ORDER BY gc.topic
    """
        )
    )

    for row in group_result:
        print(f"  GROUP: {row[0]} ({row[1]} members, {row[2]} messages)")


def print_message_timeline(conn):
    """Print recent message timeline."""
    print(f"\nMessage Timeline (last {MAX_SAMPLE_MESSAGES} messages):")

    result = conn.execute(
        text(
            f"""
        SELECT m.created_at, u.username,
               CASE
                   WHEN gc.topic IS NOT NULL THEN CONCAT('Group: ', gc.topic)
                   WHEN dm.dm_key IS NOT NULL THEN CONCAT('DM: ', dm.dm_key)
                   ELSE 'Unknown Chat'
               END as chat_name,
               LEFT(m.content, 50) as content_preview
        FROM message m
        JOIN \"user\" u ON m.sender_id = u.id
        JOIN chat c ON m.chat_id = c.id
        LEFT JOIN group_chat gc ON c.id = gc.id
        LEFT JOIN direct_message dm ON c.id = dm.id
        ORDER BY m.created_at DESC
        LIMIT {MAX_SAMPLE_MESSAGES}
    """
        )
    )

    for row in result:
        content_preview = f"{row[3]}..." if len(row[3]) == 50 else row[3]
        print(f"  {row[0]} | {row[1]} in {row[2]}: {content_preview}")


def verify_dm_key_uniqueness(conn):
    """Verify DM key uniqueness constraint."""
    result = conn.execute(
        text(
            "SELECT dm_key, COUNT(*) FROM direct_message GROUP BY dm_key HAVING COUNT(*) > 1"
        )
    )
    duplicate_dm_keys = result.fetchall()

    if duplicate_dm_keys:
        print(f"  FAIL: Found {len(duplicate_dm_keys)} duplicate DM keys!")
        for dm_key, count in duplicate_dm_keys:
            print(f"     - '{dm_key}' appears {count} times")
    else:
        print("  PASS: DM key uniqueness: OK")


def verify_membership_uniqueness(conn):
    """Verify membership uniqueness constraint."""
    result = conn.execute(
        text(
            "SELECT chat_id, user_id, COUNT(*) FROM membership GROUP BY chat_id, user_id HAVING COUNT(*) > 1"
        )
    )
    duplicate_memberships = result.fetchall()

    if duplicate_memberships:
        print(f"  FAIL: Found {len(duplicate_memberships)} duplicate memberships!")
    else:
        print("  PASS: Membership uniqueness: OK")


def verify_chat_inheritance(conn):
    """Verify chat inheritance integrity."""
    result = conn.execute(
        text(
            """
        SELECT c.id, c.type,
               CASE WHEN dm.id IS NOT NULL THEN 1 ELSE 0 END as has_dm,
               CASE WHEN gc.id IS NOT NULL THEN 1 ELSE 0 END as has_group
        FROM chat c
        LEFT JOIN direct_message dm ON c.id = dm.id
        LEFT JOIN group_chat gc ON c.id = gc.id
    """
        )
    )

    inheritance_issues = []
    for chat_id, chat_type, has_dm, has_group in result:
        if chat_type == "dm" and (has_dm != 1 or has_group != 0):
            inheritance_issues.append(f"DM chat {chat_id} has incorrect inheritance")
        elif chat_type == "group" and (has_dm != 0 or has_group != 1):
            inheritance_issues.append(f"Group chat {chat_id} has incorrect inheritance")

    if inheritance_issues:
        print("  FAIL: Chat inheritance issues:")
        for issue in inheritance_issues:
            print(f"     - {issue}")
    else:
        print("  PASS: Chat inheritance integrity: OK")


def verify_foreign_key_integrity(conn):
    """Verify foreign key integrity."""
    result = conn.execute(
        text(
            """
        SELECT
            (SELECT COUNT(*) FROM membership m LEFT JOIN "user" u ON m.user_id = u.id WHERE u.id IS NULL) as orphaned_user_memberships,
            (SELECT COUNT(*) FROM membership m LEFT JOIN chat c ON m.chat_id = c.id WHERE c.id IS NULL) as orphaned_chat_memberships,
            (SELECT COUNT(*) FROM message m LEFT JOIN "user" u ON m.sender_id = u.id WHERE u.id IS NULL) as orphaned_user_messages,
            (SELECT COUNT(*) FROM message m LEFT JOIN chat c ON m.chat_id = c.id WHERE c.id IS NULL) as orphaned_chat_messages
    """
        )
    )

    orphaned = result.fetchone()
    total_orphaned = sum(orphaned)

    if total_orphaned > 0:
        print("  FAIL: Foreign key integrity issues:")
        if orphaned[0] > 0:
            print(f"     - {orphaned[0]} memberships with invalid user_id")
        if orphaned[1] > 0:
            print(f"     - {orphaned[1]} memberships with invalid chat_id")
        if orphaned[2] > 0:
            print(f"     - {orphaned[2]} messages with invalid sender_id")
        if orphaned[3] > 0:
            print(f"     - {orphaned[3]} messages with invalid chat_id")
    else:
        print("  PASS: Foreign key integrity: OK")


def verify_data_quality(conn):
    """Verify basic data quality."""
    print("\nData Quality:")

    # Check for empty usernames
    result = conn.execute(
        text("SELECT COUNT(*) FROM \"user\" WHERE username IS NULL OR username = ''")
    )
    empty_usernames = result.scalar()

    if empty_usernames > 0:
        print(f"  FAIL: {empty_usernames} users with empty usernames")
    else:
        print("  PASS: All users have valid usernames")

    # Check for empty message content
    result = conn.execute(
        text("SELECT COUNT(*) FROM message WHERE content IS NULL OR content = ''")
    )
    empty_messages = result.scalar()

    if empty_messages > 0:
        print(f"  FAIL: {empty_messages} messages with empty content")
    else:
        print("  PASS: All messages have content")

    # Check DM key format
    result = conn.execute(
        text("SELECT dm_key FROM direct_message WHERE dm_key NOT LIKE '%::%'")
    )
    invalid_dm_keys = result.fetchall()

    if invalid_dm_keys:
        print(f"  FAIL: {len(invalid_dm_keys)} DM keys with invalid format")
    else:
        print("  PASS: All DM keys have correct format")


def run_constraint_verification(conn):
    """Run all constraint verification tests."""
    print("\nConstraint Verification:")
    verify_dm_key_uniqueness(conn)
    verify_membership_uniqueness(conn)
    verify_chat_inheritance(conn)
    verify_foreign_key_integrity(conn)


def main():
    """Main verification function."""
    database_url = get_database_url()
    engine = create_engine(database_url)

    with engine.connect() as conn:
        print_header()
        print_row_counts(conn)
        print_sample_users(conn)
        print_chat_structure(conn)
        print_message_timeline(conn)
        run_constraint_verification(conn)
        verify_data_quality(conn)

        print("\nVerification complete!")


if __name__ == "__main__":
    main()
