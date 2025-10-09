"""Conftest for service tests."""

import pytest
from sqlalchemy.orm import Session

from app.core.auth.auth_utils import get_password_hash
from app.models.user import User, UserStatus
from app.repositories.chat_repo import ChatRepo
from app.repositories.message_repo import MessageRepo
from app.repositories.user_repo import UserRepo
from app.services.chat_service import ChatService
from app.services.message_service import MessageService


@pytest.fixture
def chat_repo(test_session_factory):
    """Create ChatRepo instance."""
    return ChatRepo(test_session_factory)


@pytest.fixture
def user_repo(test_session_factory):
    """Create UserRepo instance."""
    return UserRepo(test_session_factory)


@pytest.fixture
def chat_service(chat_repo, user_repo):
    """Create ChatService instance."""
    return ChatService(chat_repo, user_repo)


@pytest.fixture
def message_repo(test_session_factory):
    """Create MessageRepo instance."""
    return MessageRepo(test_session_factory)


@pytest.fixture
def message_service(message_repo, chat_repo):
    """Create MessageService instance."""
    return MessageService(message_repo, chat_repo)


@pytest.fixture
def sample_users(test_session):
    """Create multiple test users."""
    users = [
        User(
            username="alice",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE,
        ),
        User(
            username="bob",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE,
        ),
        User(
            username="charlie",
            password_hash=get_password_hash("password123"),
            status=UserStatus.ACTIVE,
        ),
    ]

    for user in users:
        test_session.add(user)
    test_session.commit()

    for user in users:
        test_session.refresh(user)

    return users
