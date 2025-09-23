"""Chat models."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base

if TYPE_CHECKING:
    pass


class Chat(Base):
    """Base chat class."""

    __tablename__ = "chat"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())

    # Relationships
    memberships = relationship("Membership", back_populates="chat")
    messages = relationship("Message", back_populates="chat")

    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "chat",
    }

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


class DirectMessage(Chat):
    """Direct message between two users."""

    __tablename__ = "direct_message"

    id = Column(UUID(as_uuid=True), ForeignKey("chat.id"), primary_key=True)
    dm_key = Column(String, nullable=False, unique=True)

    __mapper_args__ = {
        "polymorphic_identity": "dm",
    }

    @classmethod
    def create_dm_key(cls, user1_id: uuid.UUID, user2_id: uuid.UUID) -> str:
        """Create dm_key from two user IDs ensuring consistent ordering."""
        min_id, max_id = sorted([str(user1_id), str(user2_id)])
        return f"{min_id}::{max_id}"

    @classmethod
    def find_by_users(cls, session, user1_id: uuid.UUID, user2_id: uuid.UUID):
        """Find existing DM between two users."""
        dm_key = cls.create_dm_key(user1_id, user2_id)
        return session.query(cls).filter_by(dm_key=dm_key).first()

    def __repr__(self):
        return f"<DirectMessage(id={self.id}, dm_key='{self.dm_key}')>"


class GroupChat(Chat):
    """Group chat with multiple participants."""

    __tablename__ = "group_chat"

    id = Column(UUID(as_uuid=True), ForeignKey("chat.id"), primary_key=True)
    topic = Column(String, nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "group",
    }

    def get_admins(self, session):
        """Get all admin members of this group."""
        from .membership import MemberRole, Membership

        return (
            session.query(Membership)
            .filter(Membership.chat_id == self.id, Membership.role == MemberRole.ADMIN)
            .all()
        )

    def add_admin(self, session, user_id: uuid.UUID):
        """Promote a member to admin."""
        from .membership import MemberRole, Membership

        membership = (
            session.query(Membership)
            .filter(Membership.chat_id == self.id, Membership.user_id == user_id)
            .first()
        )
        if membership:
            membership.role = MemberRole.ADMIN

    def __repr__(self):
        return f"<GroupChat(id={self.id}, topic='{self.topic}')>"
