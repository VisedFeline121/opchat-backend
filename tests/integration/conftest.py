"""Conftest for integration tests."""

from uuid import UUID

import pytest

from app.core.auth.auth_utils import get_password_hash
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepo


@pytest.fixture
def user_repo(test_session_factory):
    """Create UserRepo instance."""
    return UserRepo(test_session_factory)


@pytest.fixture
def placeholder_user(test_session):
    """Create the placeholder user that the API expects (until auth is implemented)."""
    # Create user with specific UUID
    placeholder_user = User(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        username="placeholder",
        password_hash=get_password_hash("hash123"),
        status=UserStatus.ACTIVE,
    )
    test_session.add(placeholder_user)
    test_session.commit()
    return placeholder_user
