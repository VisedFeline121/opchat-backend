"""Membership model."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.enums import MemberRole

from . import Base

if TYPE_CHECKING:
    pass


class Membership(Base):
    __tablename__ = "membership"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chat_id = Column(
        UUID(as_uuid=True), ForeignKey("chat.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(Enum(MemberRole), nullable=False, default=MemberRole.MEMBER)
    joined_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())

    # Relationships
    chat = relationship("Chat", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="membership_chat_user_unique"),
        Index("ix_membership_user_id", "user_id"),  # For "my chats" lookup
    )

    def __repr__(self):
        return f"<Membership(chat_id={self.chat_id}, user_id={self.user_id}, role={self.role})>"
