"""Authentication helper utilities for tests."""

from uuid import UUID

from app.core.auth.auth_utils import create_access_token
from app.models.user import User


def create_test_token(user_id: UUID) -> str:
    """
    Create a JWT token for testing.

    Args:
        user_id: The user ID to encode in the token

    Returns:
        A valid JWT access token
    """
    return create_access_token(user_id)


def get_auth_headers(user: User) -> dict:
    """
    Get authorization headers for a test user.

    Args:
        user: The user to create auth headers for

    Returns:
        Dictionary with Authorization header
    """
    token = create_test_token(UUID(str(user.id)))
    return {"Authorization": f"Bearer {token}"}
