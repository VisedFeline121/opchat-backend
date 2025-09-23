"""
OpChat Database Population Script

This script populates the database with deterministic test data including:
- 5 users with hashed passwords
- 2 direct message conversations
- 2 group chat conversations
- ~20 messages total

Usage:
    python scripts/db_scripts/populate.py
    make populate
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

try:
    from passlib.context import CryptContext
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("Error: Required packages not installed. Please install them first:")
    print("pip install sqlalchemy psycopg2-binary passlib[bcrypt]")
    sys.exit(1)

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
CHAT_CREATION_OFFSET_MINUTES = 150
MEMBERSHIP_JOIN_OFFSET_MINUTES = 140
EXPECTED_USER_COUNT = 5
EXPECTED_CHAT_TYPES = ["dm", "group"]
DATA_DIRECTORY = "data"

# Sample data info for summary
SAMPLE_USERS = ["alice", "bob", "charlie", "diana", "eve"]
SAMPLE_DMS = ["alice-bob", "charlie-diana"]
SAMPLE_GROUPS = ["Development Team", "Product Planning"]


def get_database_url():
    """Get database URL from environment variables."""
    return os.getenv("APP_DATABASE_URL") or os.getenv(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )


def get_password_context():
    """Get password hashing context."""
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_data_file_path(filename):
    """Get path to data file in the data directory."""
    return Path(__file__).parent / DATA_DIRECTORY / filename


def load_json_data(filename):
    """Load JSON data from the data directory."""
    data_path = get_data_file_path(filename)
    with open(data_path) as f:
        return json.load(f)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_context = get_password_context()
    return str(pwd_context.hash(password))


def create_deterministic_uuid(seed_string: str) -> uuid.UUID:
    """Create a deterministic UUID from a seed string."""
    import hashlib

    # Use SHA-256 hash of the seed string to generate deterministic bytes
    hash_bytes = hashlib.sha256(seed_string.encode()).digest()[:16]
    # Create UUID from the first 16 bytes
    return uuid.UUID(bytes=hash_bytes)


def create_single_user(user_data):
    """Create a single user from user data."""
    return User(
        id=create_deterministic_uuid(f"user_{user_data['username']}"),
        username=user_data["username"],
        password_hash=hash_password(user_data.get("password", DEFAULT_PASSWORD)),
        status=UserStatus.ACTIVE,
        created_at=datetime.now() - timedelta(days=30),
    )


def create_users(session):
    """Create users from JSON data."""
    print("Creating users...")
    users_data = load_json_data("users.json")

    users = {}
    for user_data in users_data:
        user = create_single_user(user_data)
        session.add(user)
        users[user.username] = user

    session.commit()
    print(f"  Created {len(users)} users")
    return users


def generate_chat_seed(conv_data):
    """Generate deterministic seed for chat ID."""
    if conv_data["type"] == "dm":
        participant_names = sorted(conv_data["participants"])
        return f"dm_{participant_names[0]}_{participant_names[1]}"
    else:
        return f"group_{conv_data['topic']}"


def create_direct_message_chat(conv_data, users, base_time):
    """Create a direct message chat."""
    participant_names = sorted(conv_data["participants"])
    user1 = users[participant_names[0]]
    user2 = users[participant_names[1]]
    dm_key = DirectMessage.create_dm_key(user1.id, user2.id)

    chat_seed = generate_chat_seed(conv_data)

    return DirectMessage(
        id=create_deterministic_uuid(chat_seed),
        type="dm",
        created_at=base_time - timedelta(minutes=CHAT_CREATION_OFFSET_MINUTES),
        dm_key=dm_key,
    )


def create_group_chat(conv_data, base_time):
    """Create a group chat."""
    chat_seed = generate_chat_seed(conv_data)

    return GroupChat(
        id=create_deterministic_uuid(chat_seed),
        type="group",
        created_at=base_time - timedelta(minutes=CHAT_CREATION_OFFSET_MINUTES),
        topic=conv_data["topic"],
    )


def create_chat_from_data(conv_data, users, base_time):
    """Create a chat based on conversation data."""
    if conv_data["type"] == "dm":
        return create_direct_message_chat(conv_data, users, base_time)
    elif conv_data["type"] == "group":
        return create_group_chat(conv_data, base_time)
    else:
        raise ValueError(f"Unknown conversation type: {conv_data['type']}")


def determine_member_role(conv_data, participant_name):
    """Determine the role for a participant in a chat."""
    if (
        conv_data["type"] == "group"
        and participant_name == conv_data["participants"][0]
    ):
        return MemberRole.ADMIN  # First participant in group becomes admin
    else:
        return MemberRole.MEMBER


def create_membership(chat, user, role, base_time):
    """Create a membership for a user in a chat."""
    return Membership(
        chat_id=chat.id,
        user_id=user.id,
        role=role,
        joined_at=base_time - timedelta(minutes=MEMBERSHIP_JOIN_OFFSET_MINUTES),
    )


def create_memberships_for_chat(session, chat, conv_data, users, base_time):
    """Create all memberships for a chat."""
    for participant_name in conv_data["participants"]:
        user = users[participant_name]
        role = determine_member_role(conv_data, participant_name)

        membership = create_membership(chat, user, role, base_time)
        session.add(membership)


def create_message_from_data(msg_data, msg_index, chat, users, base_time, chat_seed):
    """Create a single message from message data."""
    sender = users[msg_data["sender"]]
    message_time = base_time + timedelta(minutes=msg_data["timestamp_offset_minutes"])

    # Create deterministic message ID
    message_seed = f"msg_{chat_seed}_{msg_index}_{msg_data['sender']}"

    return Message(
        id=create_deterministic_uuid(message_seed),
        chat_id=chat.id,
        sender_id=sender.id,
        content=msg_data["content"],
        created_at=message_time,
    )


def create_messages_for_chat(session, chat, conv_data, users, base_time, chat_seed):
    """Create all messages for a chat."""
    messages_created = 0

    for msg_index, msg_data in enumerate(conv_data["messages"]):
        message = create_message_from_data(
            msg_data, msg_index, chat, users, base_time, chat_seed
        )
        session.add(message)
        messages_created += 1

    return messages_created


def create_single_conversation(session, conv_data, users, base_time):
    """Create a single conversation (chat, memberships, messages)."""
    chat_seed = generate_chat_seed(conv_data)

    # Create the chat
    chat = create_chat_from_data(conv_data, users, base_time)
    session.add(chat)
    session.flush()  # Get the chat ID

    # Create memberships
    create_memberships_for_chat(session, chat, conv_data, users, base_time)

    # Create messages
    messages_created = create_messages_for_chat(
        session, chat, conv_data, users, base_time, chat_seed
    )

    return 1, messages_created  # 1 chat created, N messages created


def create_conversations(session, users):
    """Create conversations (chats, memberships, messages) from JSON data."""
    print("Creating conversations...")
    conversations_data = load_json_data("conversations.json")

    chats_created = 0
    messages_created = 0
    base_time = datetime.now()

    for conv_data in conversations_data:
        chat_count, message_count = create_single_conversation(
            session, conv_data, users, base_time
        )
        chats_created += chat_count
        messages_created += message_count

    session.commit()
    print(f"  Created {chats_created} chats")
    print(f"  Created {messages_created} messages")
    return chats_created, messages_created


def test_dm_key_uniqueness_constraint(session):
    """Test that DM key uniqueness constraint is working."""
    try:
        # Try to create a duplicate DM
        user1 = session.query(User).filter_by(username="alice").first()
        user2 = session.query(User).filter_by(username="bob").first()

        # This should fail due to dm_key uniqueness
        duplicate_chat = Chat(id=uuid.uuid4(), type="dm")
        session.add(duplicate_chat)
        session.flush()

        duplicate_dm = DirectMessage(
            id=duplicate_chat.id, dm_key=DirectMessage.create_dm_key(user1.id, user2.id)
        )
        session.add(duplicate_dm)
        session.commit()

        print("    WARNING: DM key uniqueness constraint not working!")
        return False

    except Exception:
        print("    DM key uniqueness: OK")
        session.rollback()
        return True


def test_membership_uniqueness_constraint(session):
    """Test that membership uniqueness constraint is working."""
    try:
        # Try to create duplicate membership
        chat = session.query(Chat).first()
        user = session.query(User).first()

        duplicate_membership = Membership(
            chat_id=chat.id, user_id=user.id, role=MemberRole.MEMBER
        )
        session.add(duplicate_membership)
        session.commit()

        print("    WARNING: Membership uniqueness constraint not working!")
        return False

    except Exception:
        print("    Membership uniqueness: OK")
        session.rollback()
        return True


def test_foreign_key_constraints(session):
    """Test that foreign key constraints are working."""
    try:
        # Try to create message with non-existent chat
        invalid_message = Message(
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),  # Non-existent chat
            sender_id=session.query(User).first().id,
            content="This should fail",
        )
        session.add(invalid_message)
        session.commit()

        print("    WARNING: Foreign key constraints not working!")
        return False

    except Exception:
        print("    Foreign key constraints: OK")
        session.rollback()
        return True


def verify_constraints(session):
    """Verify that database constraints are working correctly."""
    print("Verifying constraints...")

    all_tests_passed = True
    all_tests_passed &= test_dm_key_uniqueness_constraint(session)
    all_tests_passed &= test_membership_uniqueness_constraint(session)
    all_tests_passed &= test_foreign_key_constraints(session)

    return all_tests_passed


def check_existing_data(session):
    """Check if data already exists in the database."""
    existing_users = session.query(User).count()
    existing_chats = session.query(Chat).count()
    existing_messages = session.query(Message).count()

    return existing_users, existing_chats, existing_messages


def delete_existing_data(session):
    """Delete existing data in reverse dependency order."""
    print("Clearing existing data...")

    # Delete in reverse dependency order - use synchronize_session=False for efficiency
    session.query(Message).delete(synchronize_session=False)
    session.query(Membership).delete(synchronize_session=False)
    # Delete child tables first, then parent
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


def get_final_counts(session):
    """Get final counts of created objects."""
    return {
        "memberships": session.query(Membership).count(),
        "direct_messages": session.query(DirectMessage).count(),
        "group_chats": session.query(GroupChat).count(),
    }


def print_population_summary(users, chats_created, messages_created, final_counts):
    """Print summary of population results."""
    print("\nDatabase population completed successfully!")
    print("Summary:")
    print(f"  Users: {len(users)}")
    print(f"  Chats: {chats_created}")
    print(f"  Messages: {messages_created}")
    print(f"  Memberships: {final_counts['memberships']}")
    print(f"  Direct Messages: {final_counts['direct_messages']}")
    print(f"  Group Chats: {final_counts['group_chats']}")


def print_sample_data_info():
    """Print information about the sample data created."""
    print("\nSample data created:")
    print(f"  Users: {', '.join(SAMPLE_USERS)} (password: {DEFAULT_PASSWORD})")
    print(f"  DMs: {', '.join(SAMPLE_DMS)}")
    print(f"  Groups: {', '.join(repr(group) for group in SAMPLE_GROUPS)}")


def print_population_header():
    """Print population start header."""
    print("Starting OpChat database population...")


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
        # Create all data
        users = create_users(db_session)
        chats_created, messages_created = create_conversations(db_session, users)

        # Verify constraints
        constraints_ok = verify_constraints(db_session)

        # Get final counts and print summary
        final_counts = get_final_counts(db_session)
        print_population_summary(users, chats_created, messages_created, final_counts)
        print_sample_data_info()

        if not constraints_ok:
            print("\nWARNING: Some database constraints are not working properly!")

    except Exception as e:
        print(f"Error during population: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
