"""
OpChat Database Benchmark Script

Runs performance benchmarks on the OpChat database to test:
- Message timeline queries (pagination)
- Chat member lookups
- User search performance
- Join query performance

Usage:
    python scripts/db_scripts/benchmark.py
    make bench
"""

import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import models after path setup
try:
    from app.models import Chat, Membership, Message, User
except ImportError as e:
    print(f"Error importing models: {e}")
    print(
        "Make sure you're running from the project root and models are properly defined"
    )
    sys.exit(1)

# Constants
DEFAULT_DATABASE_URL = "postgresql://opchat:opchat@postgres:5432/opchat"
DEFAULT_BENCHMARK_ITERATIONS = 5
MINIMUM_MESSAGE_COUNT_WARNING = 1000
SEPARATOR_LINE = "=" * 60

# Query limits
MESSAGE_TIMELINE_LIMIT = 50
MESSAGE_TIMELINE_OFFSET = 100
MESSAGE_SEARCH_LIMIT = 20
USER_SEARCH_LIMIT = 20
RECENT_ACTIVITY_LIMIT = 100
TOP_CHATS_LIMIT = 20

# Performance thresholds (in milliseconds)
TIMELINE_QUERY_THRESHOLD = 10
USER_LOOKUP_THRESHOLD = 5
MEMBERSHIP_QUERY_THRESHOLD = 10

# Search patterns
USERNAME_SEARCH_PATTERN = "a%"
MESSAGE_SEARCH_PATTERN = "%the%"


def get_database_url():
    """Get database URL from environment variables."""
    return os.getenv("APP_DATABASE_URL") or os.getenv(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )


def create_database_session():
    """Create and return a new database session."""
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def execute_query_with_timing(session, query):
    """Execute a query and measure execution time."""
    start_time = time.perf_counter()

    if callable(query):
        result = query()
    else:
        result = session.execute(query).fetchall()

    end_time = time.perf_counter()
    query_time = (end_time - start_time) * 1000  # Convert to milliseconds

    return result, query_time


def get_result_count(result):
    """Get the number of rows from a query result."""
    if hasattr(result, "__len__"):
        return len(result)
    elif hasattr(result, "rowcount"):
        return result.rowcount
    else:
        return "unknown"


def calculate_timing_stats(times):
    """Calculate timing statistics from a list of execution times."""
    return {"avg": sum(times) / len(times), "min": min(times), "max": max(times)}


def benchmark_single_query(session, query, iterations):
    """Run a single query multiple times and collect timing data."""
    times = []
    result = None

    for _ in range(iterations):
        result, query_time = execute_query_with_timing(session, query)
        times.append(query_time)

    stats = calculate_timing_stats(times)
    row_count = get_result_count(result)

    return stats, row_count


def benchmark_query(
    session, description, query, iterations=DEFAULT_BENCHMARK_ITERATIONS
):
    """Run a query multiple times and measure performance."""
    print(f"  {description}...")

    stats, row_count = benchmark_single_query(session, query, iterations)

    print(
        f"    Average: {stats['avg']:.2f}ms | Min: {stats['min']:.2f}ms | Max: {stats['max']:.2f}ms | Rows: {row_count}"
    )
    return stats["avg"]


def get_database_counts(session):
    """Get counts of all major entities in the database."""
    return {
        "users": session.query(User).count(),
        "chats": session.query(Chat).count(),
        "messages": session.query(Message).count(),
        "memberships": session.query(Membership).count(),
    }


def print_dataset_info(counts):
    """Print information about the dataset size."""
    print("\nDataset size:")
    print(f"  Users: {counts['users']:,}")
    print(f"  Chats: {counts['chats']:,}")
    print(f"  Messages: {counts['messages']:,}")
    print(f"  Memberships: {counts['memberships']:,}")


def print_dataset_warning(message_count):
    """Print warning if dataset is too small for meaningful benchmarks."""
    if message_count < MINIMUM_MESSAGE_COUNT_WARNING:
        print(f"\nWARNING: Only {message_count} messages in database.")
        print("For meaningful benchmarks, run 'make populate_large' first.")
        print("Continuing with available data...\n")


def print_benchmark_section_header(title):
    """Print a section header for benchmarks."""
    print("\n" + SEPARATOR_LINE)
    print(title)
    print(SEPARATOR_LINE)


def get_chat_with_most_messages(session):
    """Get the chat ID with the most messages for testing."""
    result = session.execute(
        text(
            """
        SELECT c.id FROM chat c
        JOIN message m ON c.id = m.chat_id
        GROUP BY c.id
        ORDER BY COUNT(m.id) DESC
        LIMIT 1
    """
        )
    ).fetchone()

    return result[0] if result else None


def create_message_timeline_query(chat_id):
    """Create SQL query for message timeline."""
    return text(
        f"""
        SELECT m.id, m.content, m.created_at, u.username
        FROM message m
        JOIN "user" u ON m.sender_id = u.id
        WHERE m.chat_id = '{chat_id}'
        ORDER BY m.created_at DESC
        LIMIT {MESSAGE_TIMELINE_LIMIT}
    """
    )


def create_message_timeline_pagination_query(chat_id):
    """Create SQL query for message timeline with pagination."""
    return text(
        f"""
        SELECT m.id, m.content, m.created_at, u.username
        FROM message m
        JOIN "user" u ON m.sender_id = u.id
        WHERE m.chat_id = '{chat_id}'
        ORDER BY m.created_at DESC
        LIMIT {MESSAGE_TIMELINE_LIMIT} OFFSET {MESSAGE_TIMELINE_OFFSET}
    """
    )


def create_message_search_query(chat_id):
    """Create SQL query for message search in chat."""
    return text(
        f"""
        SELECT m.id, m.content, m.created_at
        FROM message m
        WHERE m.chat_id = '{chat_id}'
        AND m.content ILIKE '{MESSAGE_SEARCH_PATTERN}'
        ORDER BY m.created_at DESC
        LIMIT {MESSAGE_SEARCH_LIMIT}
    """
    )


def create_user_search_query():
    """Create SQL query for user search by username."""
    return text(
        f"""
        SELECT id, username, created_at
        FROM "user"
        WHERE username ILIKE '{USERNAME_SEARCH_PATTERN}'
        ORDER BY username
        LIMIT {USER_SEARCH_LIMIT}
    """
    )


def create_user_chats_query(user_id):
    """Create SQL query for user's chats lookup."""
    return text(
        f"""
        SELECT c.id, c.type,
               CASE WHEN gc.topic IS NOT NULL THEN gc.topic
                    WHEN dm.dm_key IS NOT NULL THEN dm.dm_key
                    ELSE 'Unknown' END as name
        FROM membership m
        JOIN chat c ON m.chat_id = c.id
        LEFT JOIN group_chat gc ON c.id = gc.id
        LEFT JOIN direct_message dm ON c.id = dm.id
        WHERE m.user_id = '{user_id}'
        ORDER BY c.created_at DESC
    """
    )


def create_chat_members_query(chat_id):
    """Create SQL query for chat members lookup."""
    return text(
        f"""
        SELECT u.id, u.username, m.role, m.joined_at
        FROM membership m
        JOIN "user" u ON m.user_id = u.id
        WHERE m.chat_id = '{chat_id}'
        ORDER BY m.joined_at
    """
    )


def create_recent_activity_query(user_id):
    """Create SQL query for recent activity across user's chats."""
    return text(
        f"""
        SELECT c.id, c.type,
               CASE WHEN gc.topic IS NOT NULL THEN gc.topic
                    WHEN dm.dm_key IS NOT NULL THEN dm.dm_key
                    ELSE 'Unknown' END as chat_name,
               m.content, m.created_at, sender.username
        FROM membership mem
        JOIN chat c ON mem.chat_id = c.id
        LEFT JOIN group_chat gc ON c.id = gc.id
        LEFT JOIN direct_message dm ON c.id = dm.id
        JOIN message m ON c.id = m.chat_id
        JOIN "user" sender ON m.sender_id = sender.id
        WHERE mem.user_id = '{user_id}'
        ORDER BY m.created_at DESC
        LIMIT {RECENT_ACTIVITY_LIMIT}
    """
    )


def create_message_count_per_chat_query():
    """Create SQL query for message count per chat."""
    return text(
        f"""
        SELECT c.id, c.type,
               CASE WHEN gc.topic IS NOT NULL THEN gc.topic
                    WHEN dm.dm_key IS NOT NULL THEN dm.dm_key
                    ELSE 'Unknown' END as chat_name,
               COUNT(m.id) as message_count
        FROM chat c
        LEFT JOIN group_chat gc ON c.id = gc.id
        LEFT JOIN direct_message dm ON c.id = dm.id
        LEFT JOIN message m ON c.id = m.chat_id
        GROUP BY c.id, c.type, gc.topic, dm.dm_key
        ORDER BY message_count DESC
        LIMIT {TOP_CHATS_LIMIT}
    """
    )


def run_message_timeline_benchmarks(session, chat_id):
    """Run message timeline related benchmarks."""
    print_benchmark_section_header("MESSAGE TIMELINE BENCHMARKS")

    if not chat_id:
        print("  No chats with messages found, skipping timeline benchmarks")
        return

    # Timeline query with index (should be fast)
    benchmark_query(
        session,
        "Message timeline (last 50 messages) - INDEXED",
        create_message_timeline_query(chat_id),
    )

    # Timeline query with pagination
    benchmark_query(
        session,
        "Message timeline pagination (offset 100) - INDEXED",
        create_message_timeline_pagination_query(chat_id),
    )

    # Message search in chat
    benchmark_query(
        session, "Message search in chat (ILIKE)", create_message_search_query(chat_id)
    )


def run_user_membership_benchmarks(session, first_user, chat_id):
    """Run user and membership related benchmarks."""
    print_benchmark_section_header("USER & MEMBERSHIP BENCHMARKS")

    # User search by username (should be fast - indexed)
    benchmark_query(
        session, "User search by username - INDEXED", create_user_search_query()
    )

    # User's chats lookup (should be fast - indexed on membership.user_id)
    if first_user:
        benchmark_query(
            session,
            "User's chats lookup - INDEXED",
            create_user_chats_query(first_user.id),
        )

    # Chat members lookup
    if chat_id:
        benchmark_query(
            session, "Chat members lookup", create_chat_members_query(chat_id)
        )


def run_complex_join_benchmarks(session, first_user):
    """Run complex join query benchmarks."""
    print_benchmark_section_header("COMPLEX JOIN BENCHMARKS")

    # Recent activity across all user's chats
    if first_user:
        benchmark_query(
            session,
            "Recent activity across user's chats",
            create_recent_activity_query(first_user.id),
        )

    # Message count per chat
    benchmark_query(
        session, "Message count per chat", create_message_count_per_chat_query()
    )


def print_performance_summary(counts):
    """Print benchmark summary and performance expectations."""
    print_benchmark_section_header("BENCHMARK SUMMARY")

    print("\nIndex Performance:")
    print(
        f"  - Message timeline queries should be <{TIMELINE_QUERY_THRESHOLD}ms with proper indexes"
    )
    print(f"  - User lookups should be <{USER_LOOKUP_THRESHOLD}ms with username index")
    print(
        f"  - Membership queries should be <{MEMBERSHIP_QUERY_THRESHOLD}ms with user_id index"
    )

    print(
        f"\nDatabase size: {counts['users']:,} users, {counts['messages']:,} messages"
    )
    print(
        "For comprehensive benchmarks, use 'make populate_large' to generate 25k+ messages"
    )


def print_benchmark_header():
    """Print benchmark start header."""
    print("Starting OpChat database benchmarks...")


def print_completion_message():
    """Print benchmark completion message."""
    print("\nDatabase benchmarks completed successfully!")


def run_benchmarks():
    """Run all database benchmarks."""
    print_benchmark_header()

    session = create_database_session()

    try:
        # Get basic counts and print dataset info
        counts = get_database_counts(session)
        print_dataset_info(counts)
        print_dataset_warning(counts["messages"])

        # Get test data for benchmarks
        chat_id = get_chat_with_most_messages(session)
        first_user = session.query(User).first()

        # Run all benchmark suites
        run_message_timeline_benchmarks(session, chat_id)
        run_user_membership_benchmarks(session, first_user, chat_id)
        run_complex_join_benchmarks(session, first_user)

        # Print summary
        print_performance_summary(counts)

    except Exception as e:
        print(f"Error during benchmarking: {e}")
        raise
    finally:
        session.close()


def main():
    """Main benchmark function."""
    try:
        run_benchmarks()
        print_completion_message()

    except Exception as e:
        print(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
