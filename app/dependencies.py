"""FastAPI dependencies for dependency injection."""

from app.db.db import get_session_local
from app.repositories.chat_repo import ChatRepo
from app.repositories.user_repo import UserRepo
from app.services.chat_service import ChatService


def get_user_repo() -> UserRepo:
    """Get UserRepo instance with session factory."""
    return UserRepo(get_session_local())


def get_chat_repo() -> ChatRepo:
    """Get ChatRepo instance with session factory."""
    return ChatRepo(get_session_local())


def get_chat_service() -> ChatService:
    """Get ChatService instance with dependencies."""
    chat_repo = get_chat_repo()
    user_repo = get_user_repo()
    return ChatService(chat_repo, user_repo)
