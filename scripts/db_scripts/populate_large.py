"""
OpChat Large Scale Database Population Script

Generates realistic volume data for performance testing and benchmarking:
- 100-500 users with realistic usernames
- 50-200 group chats with varied membership
- 100-500 direct message conversations
- 10,000-50,000 messages spread over 3-6 months
- Realistic message patterns (busy hours, quiet periods)

Usage:
    python scripts/db_scripts/populate_large.py
    make populate_large
"""

import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import models after path setup
try:
    from app.models import Chat, DirectMessage, GroupChat, Membership, Message, User
    from app.models.membership import MemberRole
    from app.models.user import UserStatus
except ImportError as e:
    print(f"Error importing models: {e}")
    print(
        "Make sure you're running from the project root and models are properly defined"
    )
    sys.exit(1)

# Constants
DEFAULT_DATABASE_URL = "postgresql://opchat:opchat@postgres:5432/opchat"
DEFAULT_PASSWORD = "password123"

# Population configuration
USER_COUNT = 200
GROUP_CHAT_COUNT = 75
DM_CONVERSATION_COUNT = 300
MESSAGE_COUNT = 25000
MESSAGE_TIME_SPAN_DAYS = 120  # 4 months
ACTIVE_USER_RATIO = 0.7  # 70% of users are active message senders

# Batch sizes for performance
USER_BATCH_SIZE = 50
GROUP_CHAT_BATCH_SIZE = 25
DM_BATCH_SIZE = 100
MESSAGE_BATCH_SIZE = 1000

# Chat configuration
MIN_GROUP_MEMBERS = 3
MAX_GROUP_MEMBERS = 15
ADMIN_PROMOTION_CHANCE = 0.1  # 10% chance for additional admins
BUSINESS_HOURS_MESSAGE_RATIO = 0.7  # 70% of messages during business hours
BUSINESS_HOUR_START = 9
BUSINESS_HOUR_END = 18

# User creation constants
MIN_USER_ACCOUNT_AGE_DAYS = 1
MAX_USER_ACCOUNT_AGE_DAYS = 180

# Chat creation constants
MIN_CHAT_AGE_DAYS = 1
MAX_GROUP_CHAT_AGE_DAYS = 120
MAX_DM_CHAT_AGE_DAYS = 90

# Message timing constants
MAX_MEMBERSHIP_JOIN_DELAY_MINUTES = 60

# Username generation data
FIRST_NAMES = [
    "alex",
    "sam",
    "jordan",
    "taylor",
    "casey",
    "morgan",
    "riley",
    "avery",
    "jamie",
    "drew",
    "blake",
    "sage",
    "quinn",
    "rowan",
    "phoenix",
    "river",
    "skylar",
    "dakota",
    "cameron",
    "emery",
    "hayden",
    "kendall",
    "logan",
    "parker",
    "reese",
    "charlie",
    "finley",
    "harper",
    "indigo",
    "justice",
    "kai",
    "lane",
    "marley",
    "nova",
    "ocean",
    "peyton",
    "raven",
    "scout",
    "storm",
    "tate",
    "val",
    "wren",
    "zion",
    "aria",
    "brook",
    "cleo",
    "dani",
    "echo",
    "fern",
    "gray",
    "iris",
    "jade",
    "knox",
    "luna",
    "max",
    "noel",
    "onyx",
    "rain",
    "sage",
    "true",
    "vega",
    "west",
    "yale",
    "zen",
]

LAST_PARTS = [
    "dev",
    "code",
    "tech",
    "pro",
    "user",
    "chat",
    "msg",
    "talk",
    "comm",
    "link",
    "net",
    "web",
    "app",
    "sys",
    "hub",
    "lab",
    "box",
    "bit",
    "byte",
    "data",
    "info",
    "core",
    "sync",
    "flow",
    "stream",
    "pulse",
    "wave",
    "spark",
    "bolt",
    "dash",
    "zoom",
    "ping",
    "echo",
    "beam",
    "glow",
    "nova",
    "star",
    "moon",
    "sun",
    "sky",
    "cloud",
    "storm",
    "wind",
]

# Group name generation data
TEAM_TYPES = ["Team", "Squad", "Crew", "Group", "Circle", "Club", "Gang"]
PROJECTS = [
    "Alpha",
    "Beta",
    "Gamma",
    "Phoenix",
    "Storm",
    "Thunder",
    "Lightning",
    "Rocket",
]
DEPARTMENTS = [
    "Engineering",
    "Design",
    "Marketing",
    "Sales",
    "Support",
    "DevOps",
    "QA",
    "Product",
]
CASUAL_GROUPS = [
    "Coffee Chat",
    "Random",
    "General",
    "Watercooler",
    "Lunch Crew",
    "Gaming",
    "Music",
    "Books",
]

# Message content templates
MESSAGE_TEMPLATES = [
    "Hey everyone! How's it going?",
    "Just finished the meeting, here are the key points:",
    "Can someone help me with this issue?",
    "Great work on the latest update!",
    "I'll be out of office tomorrow",
    "Let's schedule a quick sync",
    "Thanks for the quick response",
    "Looking forward to the presentation",
    "The deployment went smoothly",
    "Anyone free for a coffee break?",
    "I've updated the documentation",
    "The test results look good",
    "We should discuss this further",
    "I'll send the details via email",
    "Perfect timing on that fix",
    "The client feedback was positive",
    "Let me know if you need anything",
    "I'm working on the new feature",
    "The performance improvements are noticeable",
    "Good catch on that bug!",
    "I'll review the code changes",
    "The integration is working well",
    "We're ahead of schedule",
    "I'll handle the deployment",
    "Thanks for the collaboration",
    "The design looks fantastic",
    "I've tested the new functionality",
    "Let's wrap up this sprint",
    "The metrics are looking positive",
    "I'll coordinate with the team",
]


def get_database_url():
    """Get database URL from environment variables."""
    return os.getenv("APP_DATABASE_URL") or os.getenv(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )


def get_password_context():
    """Get password hashing context."""
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_context = get_password_context()
    return str(pwd_context.hash(password))


def create_deterministic_uuid(seed_string: str) -> uuid.UUID:
    """Create a deterministic UUID from a seed string."""
    import hashlib

    hash_bytes = hashlib.sha256(seed_string.encode()).digest()[:16]
    return uuid.UUID(bytes=hash_bytes)


def generate_username_pattern():
    """Generate a username using various realistic patterns."""
    patterns = [
        lambda: random.choice(FIRST_NAMES),
        lambda: f"{random.choice(FIRST_NAMES)}{random.randint(10, 99)}",
        lambda: f"{random.choice(FIRST_NAMES)}_{random.choice(LAST_PARTS)}",
        lambda: f"{random.choice(FIRST_NAMES)}{random.choice(LAST_PARTS)}",
        lambda: f"{random.choice(LAST_PARTS)}_{random.choice(FIRST_NAMES)}",
    ]
    return random.choice(patterns)()


def generate_group_name_pattern():
    """Generate a group chat name using various realistic patterns."""
    patterns = [
        lambda: f"{random.choice(PROJECTS)} {random.choice(TEAM_TYPES)}",
        lambda: f"{random.choice(DEPARTMENTS)} {random.choice(TEAM_TYPES)}",
        lambda: random.choice(CASUAL_GROUPS),
        lambda: f"Project {random.choice(PROJECTS)}",
        lambda: f"{random.choice(DEPARTMENTS)} Discussion",
    ]
    return random.choice(patterns)()


def ensure_unique_username(base_username, used_usernames):
    """Ensure username is unique by appending numbers if needed."""
    username = base_username
    counter = 1

    while username in used_usernames:
        username = f"{base_username}{counter}"
        counter += 1

    return username


def ensure_unique_group_name(base_name, existing_groups):
    """Ensure group name is unique by appending numbers if needed."""
    group_name = base_name
    counter = 1

    while any(gc.topic == group_name for gc in existing_groups):
        group_name = f"{base_name} {counter}"
        counter += 1

    return group_name


def create_single_user(username, index):
    """Create a single user with realistic data."""
    return User(
        id=create_deterministic_uuid(f"large_user_{username}"),
        username=username,
        password_hash=hash_password(DEFAULT_PASSWORD),
        status=UserStatus.ACTIVE,
        created_at=datetime.now()
        - timedelta(
            days=random.randint(MIN_USER_ACCOUNT_AGE_DAYS, MAX_USER_ACCOUNT_AGE_DAYS)
        ),
    )


def check_existing_data(session):
    """Check if data already exists in the database."""
    existing_users = session.query(User).count()
    existing_chats = session.query(Chat).count()
    existing_messages = session.query(Message).count()

    return existing_users, existing_chats, existing_messages


def delete_existing_data(session):
    """Delete existing data in reverse dependency order."""
    print("Clearing existing data...")

    # Delete in reverse dependency order
    session.query(Message).delete(synchronize_session=False)
    session.query(Membership).delete(synchronize_session=False)
    session.query(GroupChat).delete(synchronize_session=False)
    session.query(DirectMessage).delete(synchronize_session=False)
    session.query(Chat).delete(synchronize_session=False)
    session.query(User).delete(synchronize_session=False)

    session.commit()
    print("Existing data cleared.")


def clear_existing_data(session):
    """Clear existing data to allow clean population."""
    print("Checking for existing data...")

    existing_users, existing_chats, existing_messages = check_existing_data(session)

    if existing_users > 0 or existing_chats > 0 or existing_messages > 0:
        print(
            f"Found existing data: {existing_users} users, {existing_chats} chats, {existing_messages} messages"
        )
        delete_existing_data(session)
    else:
        print("No existing data found.")


def create_users(session):
    """Create realistic users."""
    print(f"Creating {USER_COUNT} users...")

    users = {}
    used_usernames = set()

    for i in range(USER_COUNT):
        base_username = generate_username_pattern()
        username = ensure_unique_username(base_username, used_usernames)
        used_usernames.add(username)

        user = create_single_user(username, i)
        session.add(user)
        users[username] = user

        # Commit in batches for performance
        if (i + 1) % USER_BATCH_SIZE == 0:
            session.commit()
            print(f"  Created {i + 1}/{USER_COUNT} users")

    session.commit()
    print(f"  Created {len(users)} users total")
    return users


def determine_member_role(member_index, is_first_member):
    """Determine the role for a group member."""
    if is_first_member:
        return MemberRole.ADMIN  # First member is always admin
    elif random.random() < ADMIN_PROMOTION_CHANCE:
        return MemberRole.ADMIN  # Random chance for additional admins
    else:
        return MemberRole.MEMBER


def create_group_memberships(session, chat, members):
    """Create memberships for a group chat."""
    for j, user in enumerate(members):
        is_first_member = j == 0
        role = determine_member_role(j, is_first_member)

        membership = Membership(
            chat_id=chat.id,
            user_id=user.id,
            role=role,
            joined_at=chat.created_at
            + timedelta(minutes=random.randint(0, MAX_MEMBERSHIP_JOIN_DELAY_MINUTES)),
        )
        session.add(membership)


def create_single_group_chat(session, group_name, user_list):
    """Create a single group chat with members."""
    chat = GroupChat(
        id=create_deterministic_uuid(f"large_group_{group_name}"),
        type="group",
        created_at=datetime.now()
        - timedelta(days=random.randint(MIN_CHAT_AGE_DAYS, MAX_GROUP_CHAT_AGE_DAYS)),
        topic=group_name,
    )
    session.add(chat)
    session.flush()  # Get the chat ID

    # Add members (3-15 members per group)
    member_count = random.randint(
        MIN_GROUP_MEMBERS, min(MAX_GROUP_MEMBERS, len(user_list))
    )
    members = random.sample(user_list, member_count)

    create_group_memberships(session, chat, members)

    return chat


def create_group_chats(session, users):
    """Create group chats with varied membership."""
    print(f"Creating {GROUP_CHAT_COUNT} group chats...")

    user_list = list(users.values())
    group_chats = []

    for i in range(GROUP_CHAT_COUNT):
        base_name = generate_group_name_pattern()
        group_name = ensure_unique_group_name(base_name, group_chats)

        chat = create_single_group_chat(session, group_name, user_list)
        group_chats.append(chat)

        # Commit in batches
        if (i + 1) % GROUP_CHAT_BATCH_SIZE == 0:
            session.commit()
            print(f"  Created {i + 1}/{GROUP_CHAT_COUNT} group chats")

    session.commit()
    print(f"  Created {len(group_chats)} group chats total")
    return group_chats


def create_dm_memberships(session, chat, user1, user2):
    """Create memberships for a DM chat."""
    for user in [user1, user2]:
        membership = Membership(
            chat_id=chat.id,
            user_id=user.id,
            role=MemberRole.MEMBER,
            joined_at=chat.created_at,
        )
        session.add(membership)


def create_single_dm_chat(session, user1, user2):
    """Create a single DM chat between two users."""
    dm_key = DirectMessage.create_dm_key(user1.id, user2.id)

    chat = DirectMessage(
        id=create_deterministic_uuid(f"large_dm_{dm_key}"),
        type="dm",
        created_at=datetime.now()
        - timedelta(days=random.randint(MIN_CHAT_AGE_DAYS, MAX_DM_CHAT_AGE_DAYS)),
        dm_key=dm_key,
    )
    session.add(chat)
    session.flush()

    create_dm_memberships(session, chat, user1, user2)

    return chat


def create_direct_messages(session, users):
    """Create direct message conversations."""
    print(f"Creating {DM_CONVERSATION_COUNT} DM conversations...")

    user_list = list(users.values())
    dm_chats = []
    used_pairs = set()

    attempts = 0
    max_attempts = DM_CONVERSATION_COUNT * 2  # Prevent infinite loops

    while len(dm_chats) < DM_CONVERSATION_COUNT and attempts < max_attempts:
        user1, user2 = random.sample(user_list, 2)

        # Ensure unique pairs
        pair_key = tuple(sorted([user1.id, user2.id]))
        if pair_key in used_pairs:
            attempts += 1
            continue

        used_pairs.add(pair_key)

        chat = create_single_dm_chat(session, user1, user2)
        dm_chats.append(chat)

        # Commit in batches
        if len(dm_chats) % DM_BATCH_SIZE == 0:
            session.commit()
            print(f"  Created {len(dm_chats)}/{DM_CONVERSATION_COUNT} DM conversations")

        attempts += 1

    session.commit()
    print(f"  Created {len(dm_chats)} DM conversations total")
    return dm_chats


def generate_message_content():
    """Generate realistic message content."""
    return random.choice(MESSAGE_TEMPLATES)


def generate_realistic_message_time(start_date, days_span):
    """Generate a realistic message timestamp with business hours bias."""
    days_offset = random.randint(0, days_span)
    base_time = start_date + timedelta(days=days_offset)

    # Business hours bias (9 AM - 6 PM gets 70% of messages)
    if random.random() < BUSINESS_HOURS_MESSAGE_RATIO:
        hour = random.randint(BUSINESS_HOUR_START, BUSINESS_HOUR_END)
    else:
        hour = random.randint(0, 23)

    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    return base_time.replace(hour=hour, minute=minute, second=second)


def get_chat_weight(session, chat):
    """Calculate message weight for a chat based on member count."""
    member_count = session.query(Membership).filter_by(chat_id=chat.id).count()
    return max(1, member_count // 2)  # Groups get more messages


def create_weighted_chat_list(session, all_chats):
    """Create a weighted list of chats for message distribution."""
    weighted_chats = []

    for chat in all_chats:
        weight = get_chat_weight(session, chat)
        weighted_chats.extend([chat] * weight)

    return weighted_chats


def get_active_chat_users(session, chat, active_users):
    """Get active users who are members of the chat."""
    memberships = session.query(Membership).filter_by(chat_id=chat.id).all()
    return [m.user for m in memberships if m.user in active_users]


def create_single_message(chat, sender, message_index, message_time):
    """Create a single message."""
    return Message(
        id=create_deterministic_uuid(
            f"large_msg_{chat.id}_{message_index}_{sender.id}"
        ),
        chat_id=chat.id,
        sender_id=sender.id,
        content=generate_message_content(),
        created_at=message_time,
    )


def create_messages(session, all_chats, users):
    """Create realistic messages with time patterns."""
    print(f"Creating {MESSAGE_COUNT} messages...")

    user_list = list(users.values())
    active_users = random.sample(user_list, int(len(user_list) * ACTIVE_USER_RATIO))

    # Weight chats by member count (more members = more messages)
    weighted_chats = create_weighted_chat_list(session, all_chats)

    messages_created = 0
    start_date = datetime.now() - timedelta(days=MESSAGE_TIME_SPAN_DAYS)

    for i in range(MESSAGE_COUNT):
        chat = random.choice(weighted_chats)

        # Get active chat members
        chat_users = get_active_chat_users(session, chat, active_users)

        if not chat_users:
            continue

        sender = random.choice(chat_users)
        message_time = generate_realistic_message_time(
            start_date, MESSAGE_TIME_SPAN_DAYS
        )

        message = create_single_message(chat, sender, i, message_time)
        session.add(message)
        messages_created += 1

        # Commit in batches for performance
        if (i + 1) % MESSAGE_BATCH_SIZE == 0:
            session.commit()
            print(f"  Created {i + 1}/{MESSAGE_COUNT} messages")

    session.commit()
    print(f"  Created {messages_created} messages total")
    return messages_created


def get_final_counts(session):
    """Get final counts of created objects."""
    return session.query(Membership).count()


def calculate_performance_metrics(start_time, end_time, messages_created):
    """Calculate performance metrics."""
    duration = (end_time - start_time).total_seconds()
    messages_per_second = messages_created / duration if duration > 0 else 0

    return duration, messages_per_second


def print_population_header():
    """Print population start header with configuration."""
    print("Starting OpChat large-scale database population...")
    print(
        f"Configuration: {USER_COUNT} users, {GROUP_CHAT_COUNT} groups, {DM_CONVERSATION_COUNT} DMs, {MESSAGE_COUNT} messages"
    )


def print_population_summary(
    users, group_chats, dm_chats, messages_created, membership_count
):
    """Print summary of population results."""
    print("\nLarge-scale database population completed successfully!")
    print("Summary:")
    print(f"  - Users: {len(users):,}")
    print(f"  - Group Chats: {len(group_chats):,}")
    print(f"  - DM Chats: {len(dm_chats):,}")
    print(f"  - Total Chats: {len(group_chats) + len(dm_chats):,}")
    print(f"  - Messages: {messages_created:,}")
    print(f"  - Memberships: {membership_count:,}")


def print_performance_metrics(duration, messages_per_second):
    """Print performance metrics."""
    print(f"\nExecution time: {duration:.1f} seconds")
    print(f"Messages per second: {messages_per_second:.0f}")


def print_usage_info():
    """Print information about what the test data is useful for."""
    print("\nRealistic test data created for:")
    print("  - Performance testing")
    print("  - Load testing")
    print("  - Message timeline benchmarks")
    print("  - Search functionality testing")
    print("  - Pagination testing")


def create_database_session():
    """Create and return a new database session."""
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def main():
    """Main population function."""
    print_population_header()

    # Use separate session for clearing to avoid state issues
    clear_session = create_database_session()
    try:
        clear_existing_data(clear_session)
    finally:
        clear_session.close()

    # Create fresh session for population
    db_session = create_database_session()
    try:
        start_time = datetime.now()

        # Create all data
        users = create_users(db_session)
        group_chats = create_group_chats(db_session, users)
        dm_chats = create_direct_messages(db_session, users)
        all_chats = group_chats + dm_chats
        messages_created = create_messages(db_session, all_chats, users)

        end_time = datetime.now()

        # Get final counts and calculate metrics
        membership_count = get_final_counts(db_session)
        duration, messages_per_second = calculate_performance_metrics(
            start_time, end_time, messages_created
        )

        # Print results
        print_population_summary(
            users, group_chats, dm_chats, messages_created, membership_count
        )
        print_performance_metrics(duration, messages_per_second)
        print_usage_info()

    except Exception as e:
        print(f"Error during population: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
