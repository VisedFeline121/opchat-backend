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


# Placeholder user fixture removed - authentication now uses JWT tokens
