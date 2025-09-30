"""Message repository."""

from datetime import datetime
from typing import List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging.logging import get_logger
from app.models.message import Message
from app.repositories.base_repo import BaseRepo

logger = get_logger(__name__)


class MessageRepo(BaseRepo):
    """Message repository."""

    def _create_message_implementation(
        self,
        session: Session,
        chat_id: UUID,
        sender_id: UUID,
        content: str,
        idempotency_key: str,
    ) -> Message:
        """Implementation of message creation."""
        logger.debug(
            f"Creating message in chat {chat_id} from user {sender_id} with key {idempotency_key}"
        )

        # Check idempotency first
        existing = (
            session.query(Message)
            .filter(Message.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            logger.debug(
                f"Returning existing message for idempotency key {idempotency_key}: {existing.id}"
            )
            return existing

        # Create new message
        message = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            idempotency_key=idempotency_key,
        )
        session.add(message)
        session.flush()

        logger.info(
            f"Created message: {message.id} in chat {chat_id} from user {sender_id}"
        )
        return message

    def create_message(
        self,
        chat_id: UUID,
        sender_id: UUID,
        content: str,
        idempotency_key: str,
        session: Optional[Session] = None,
    ) -> Message:
        """Create a new message with idempotency support."""
        return cast(
            Message,
            self._execute_with_session(
                lambda s: self._create_message_implementation(
                    s, chat_id, sender_id, content, idempotency_key
                ),
                session=session,
                operation_name="create_message",
            ),
        )

    def _get_chat_history_implementation(
        self,
        session: Session,
        chat_id: UUID,
        after_timestamp: Optional[datetime],
        limit: int,
    ) -> List[Message]:
        """Implementation of chat history retrieval."""
        # Validate inputs
        if limit < 0:
            raise ValueError("Limit must be non-negative")
        if limit == 0:
            return []

        query = session.query(Message).filter(Message.chat_id == chat_id)

        if after_timestamp:
            query = query.filter(Message.created_at > after_timestamp)

        return cast(
            List[Message], query.order_by(Message.created_at.asc()).limit(limit).all()
        )

    def get_chat_history(
        self,
        chat_id: UUID,
        after_timestamp: Optional[datetime] = None,
        limit: int = 50,
        session: Optional[Session] = None,
    ) -> List[Message]:
        """Get chat message history with cursor-based pagination (forward)."""
        return cast(
            List[Message],
            self._execute_with_session(
                lambda s: self._get_chat_history_implementation(
                    s, chat_id, after_timestamp, limit
                ),
                session=session,
                operation_name="get_chat_history",
            ),
        )

    def _get_chat_history_before_implementation(
        self, session: Session, chat_id: UUID, before_timestamp: datetime, limit: int
    ) -> List[Message]:
        """Implementation of chat history retrieval before a timestamp."""
        # Validate inputs
        if limit < 0:
            raise ValueError("Limit must be non-negative")
        if limit == 0:
            return []

        return cast(
            List[Message],
            (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .filter(Message.created_at < before_timestamp)
                .order_by(Message.created_at.desc())  # Most recent first
                .limit(limit)
                .all()
            ),
        )

    def get_chat_history_before(
        self,
        chat_id: UUID,
        before_timestamp: datetime,
        limit: int = 50,
        session: Optional[Session] = None,
    ) -> List[Message]:
        """Get chat message history before a timestamp (backward pagination)."""
        return cast(
            List[Message],
            self._execute_with_session(
                lambda s: self._get_chat_history_before_implementation(
                    s, chat_id, before_timestamp, limit
                ),
                session=session,
                operation_name="get_chat_history_before",
            ),
        )

    def _get_by_idempotency_key_implementation(
        self, session: Session, idempotency_key: str
    ) -> Optional[Message]:
        """Implementation of message retrieval by idempotency key."""
        return cast(
            Optional[Message],
            (
                session.query(Message)
                .filter(Message.idempotency_key == idempotency_key)
                .first()
            ),
        )

    def get_by_idempotency_key(
        self, idempotency_key: str, session: Optional[Session] = None
    ) -> Optional[Message]:
        """Get a message by idempotency key."""
        return cast(
            Optional[Message],
            self._execute_with_session(
                lambda s: self._get_by_idempotency_key_implementation(
                    s, idempotency_key
                ),
                session=session,
                operation_name="get_by_idempotency_key",
            ),
        )

    def _get_message_by_id_implementation(
        self, session: Session, message_id: UUID
    ) -> Optional[Message]:
        """Implementation of message retrieval by ID."""
        return cast(
            Optional[Message],
            session.query(Message).filter(Message.id == message_id).one_or_none(),
        )

    def get_message_by_id(
        self, message_id: UUID, session: Optional[Session] = None
    ) -> Optional[Message]:
        """Get a message by ID."""
        return cast(
            Optional[Message],
            self._execute_with_session(
                lambda s: self._get_message_by_id_implementation(s, message_id),
                session=session,
                operation_name="get_message_by_id",
            ),
        )

    def _get_recent_messages_implementation(
        self, session: Session, chat_id: UUID, limit: int
    ) -> List[Message]:
        """Implementation of recent messages retrieval."""
        # Validate inputs
        if limit < 0:
            raise ValueError("Limit must be non-negative")
        if limit == 0:
            return []

        return cast(
            List[Message],
            (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
                .all()
            ),
        )

    def get_recent_messages(
        self, chat_id: UUID, limit: int = 50, session: Optional[Session] = None
    ) -> List[Message]:
        """Get most recent messages from a chat."""
        return cast(
            List[Message],
            self._execute_with_session(
                lambda s: self._get_recent_messages_implementation(s, chat_id, limit),
                session=session,
                operation_name="get_recent_messages",
            ),
        )
