"""FastAPI dependencies for dependency injection."""

from app.db.db import get_session_local
from app.repositories.user_repo import UserRepo


def get_user_repo() -> UserRepo:
    """Get UserRepo instance with session factory."""
    return UserRepo(get_session_local())
