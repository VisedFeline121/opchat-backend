"""Message model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base

if TYPE_CHECKING:
    pass


class Message(Base):
    __tablename__ = "message"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(
        UUID(as_uuid=True), ForeignKey("chat.id", ondelete="CASCADE"), nullable=False
    )
    sender_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")

    __table_args__ = (
        Index("ix_message_chat_created", "chat_id", "created_at"),  # Timeline paging
        Index("ix_message_sender_created", "sender_id", "created_at"),  # Audit queries
    )

    def __repr__(self):
        return f"<Message(id={self.id}, chat_id={self.chat_id}, sender_id={self.sender_id})>"
