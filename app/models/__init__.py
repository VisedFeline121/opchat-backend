"""SQLAlchemy models for OpChat."""

from typing import Any

from sqlalchemy.ext.declarative import declarative_base

# Create the declarative base
Base: Any = declarative_base()

# Import all models so they're registered with Base.metadata
from .chat import Chat, DirectMessage, GroupChat  # noqa: E402
from .membership import Membership  # noqa: E402
from .message import Message  # noqa: E402
from .user import User  # noqa: E402

__all__ = [
    "Base",
    "User",
    "Chat",
    "DirectMessage",
    "GroupChat",
    "Membership",
    "Message",
]
