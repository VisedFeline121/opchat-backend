"""User model."""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base

if TYPE_CHECKING:
    pass


class UserStatus(enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    last_login_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())

    # Relationships
    memberships = relationship("Membership", back_populates="user")
    sent_messages = relationship("Message", back_populates="sender")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', status={self.status})>"
