"""Main conftest.py for integration tests."""

import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.auth.auth_utils import get_password_hash
from app.main import app
from app.models import Base
from app.models.user import User, UserStatus
from app.models.chat import Chat, DirectMessage, GroupChat
from app.models.membership import Membership
from app.models.message import Message
from app.repositories.user_repo import UserRepo

# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://opchat_test_user:test_password@localhost:5433/opchat_test",
)

# Set test environment variables
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5433"
os.environ["POSTGRES_DB"] = "opchat_test"
os.environ["POSTGRES_USER"] = "opchat_test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_PASSWORD"] = "test_redis_password"
os.environ["RABBITMQ_HOST"] = "localhost"
os.environ["RABBITMQ_PORT"] = "5672"
os.environ["RABBITMQ_USER"] = "test_user"
os.environ["RABBITMQ_PASSWORD"] = "test_password"


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
        expire_on_commit=False,
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
def db_session(test_session_factory):
    """Create a clean database session for each test."""
    session = test_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_db(test_session):
    """Automatically clean database state before each test."""
    # Delete all data in reverse dependency order
    test_session.query(Message).delete()
    test_session.query(Membership).delete()
    test_session.query(DirectMessage).delete()
    test_session.query(GroupChat).delete()
    test_session.query(Chat).delete()
    test_session.query(User).delete()
    test_session.commit()


@pytest.fixture
def test_user(test_session_factory):
    """Create a test user in the database."""
    user_repo = UserRepo(test_session_factory)
    user = user_repo.create_user(
        username="testuser123", password_hash=get_password_hash("TestPassword123")
    )
    return user
