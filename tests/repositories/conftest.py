"""Shared fixtures for repository tests."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Chat, DirectMessage, GroupChat, Membership, Message, User
from app.models.membership import MemberRole
from app.models.user import UserStatus
from app.repositories import ChatRepo, MessageRepo, UserRepo

# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://opchat_test_user:test_password@localhost:5433/opchat_test",
)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine and tables once per session."""
    engine = create_engine(TEST_DATABASE_URL)
    # Drop and create tables to ensure a clean schema
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE;"))
        connection.execute(text("CREATE SCHEMA public;"))
        connection.commit()
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """Create session factory for tests."""
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
        expire_on_commit=False,  # Prevent DetachedInstanceError
    )


@pytest.fixture
def test_session(test_session_factory):
    """Create a clean database session for each test."""
    session = test_session_factory()

    try:
        yield session
    finally:
        # Rollback any uncommitted changes and close
        session.rollback()
        session.close()


@pytest.fixture
def clean_db(test_session):
    """Ensure clean database state for each test."""
    # Delete all data in reverse dependency order
    test_session.query(Message).delete()
    test_session.query(Membership).delete()
    test_session.query(DirectMessage).delete()
    test_session.query(GroupChat).delete()
    test_session.query(Chat).delete()
    test_session.query(User).delete()
    test_session.commit()


# Repository fixtures
@pytest.fixture
def user_repo(test_session_factory):
    """UserRepo instance with test session factory."""
    return UserRepo(test_session_factory)


@pytest.fixture
def chat_repo(test_session_factory):
    """ChatRepo instance with test session factory."""
    return ChatRepo(test_session_factory)


@pytest.fixture
def message_repo(test_session_factory):
    """MessageRepo instance with test session factory."""
    return MessageRepo(test_session_factory)


# Test data factories
@pytest.fixture
def sample_user(test_session, clean_db):
    """Create a test user."""
    user = User(
        username="testuser",
        password_hash="hashed_password_123",
        status=UserStatus.ACTIVE,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def sample_users(test_session, clean_db):
    """Create multiple test users."""
    users = [
        User(username="alice", password_hash="hash1", status=UserStatus.ACTIVE),
        User(username="bob", password_hash="hash2", status=UserStatus.ACTIVE),
        User(username="charlie", password_hash="hash3", status=UserStatus.ACTIVE),
    ]

    for user in users:
        test_session.add(user)
    test_session.commit()

    for user in users:
        test_session.refresh(user)

    return users


@pytest.fixture
def sample_dm(test_session, sample_users):
    """Create a test direct message with memberships."""
    alice, bob = sample_users[0], sample_users[1]

    # Create DM
    dm_key = DirectMessage.create_dm_key(alice.id, bob.id)
    dm = DirectMessage(dm_key=dm_key)
    test_session.add(dm)
    test_session.flush()

    # Add memberships
    membership1 = Membership(chat_id=dm.id, user_id=alice.id, role=MemberRole.MEMBER)
    membership2 = Membership(chat_id=dm.id, user_id=bob.id, role=MemberRole.MEMBER)
    test_session.add(membership1)
    test_session.add(membership2)
    test_session.commit()
    test_session.refresh(dm)

    return dm


@pytest.fixture
def sample_group_chat(test_session, sample_users):
    """Create a test group chat with memberships."""
    alice, bob, charlie = sample_users

    # Create group chat
    group = GroupChat(topic="Test Group")
    test_session.add(group)
    test_session.flush()

    # Add memberships (alice as admin, others as members)
    memberships = [
        Membership(chat_id=group.id, user_id=alice.id, role=MemberRole.ADMIN),
        Membership(chat_id=group.id, user_id=bob.id, role=MemberRole.MEMBER),
        Membership(chat_id=group.id, user_id=charlie.id, role=MemberRole.MEMBER),
    ]

    for membership in memberships:
        test_session.add(membership)

    test_session.commit()
    test_session.refresh(group)

    return group


@pytest.fixture
def sample_messages(test_session, sample_dm, sample_users):
    """Create test messages in a chat."""
    alice, bob = sample_users[0], sample_users[1]

    # Create messages with different timestamps
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    messages = []
    for i in range(5):
        message = Message(
            chat_id=sample_dm.id,
            sender_id=alice.id if i % 2 == 0 else bob.id,
            content=f"Test message {i + 1}",
            idempotency_key=f"test_key_{i + 1}",
            created_at=base_time.replace(minute=i * 10),  # 10 min intervals
        )
        messages.append(message)
        test_session.add(message)

    test_session.commit()

    for message in messages:
        test_session.refresh(message)

    return messages


# Utility fixtures
@pytest.fixture
def uuid_generator():
    """Generate test UUIDs."""

    def _generate():
        return uuid4()

    return _generate


@pytest.fixture
def timestamp_generator():
    """Generate test timestamps."""

    def _generate(offset_minutes=0):
        base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return base.replace(minute=offset_minutes)

    return _generate


@pytest.fixture
def idempotency_key_generator():
    """Generate test idempotency keys."""

    def _generate(suffix=""):
        return f"test_idem_key_{uuid4().hex[:8]}_{suffix}"

    return _generate
