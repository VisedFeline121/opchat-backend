"""Message service for business logic."""

from datetime import datetime
from typing import List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging.logging import get_logger
from app.models.message import Message
from app.repositories.chat_repo import ChatRepo
from app.repositories.message_repo import MessageRepo

logger = get_logger(__name__)

# Business rules constants
MAX_MESSAGE_LENGTH = 4000
MIN_MESSAGE_LENGTH = 1


class MessageService:
    """Message service for business logic."""

    def __init__(self, message_repo: MessageRepo, chat_repo: ChatRepo):
        """Initialize the message service."""
        self.message_repo = message_repo
        self.chat_repo = chat_repo

    def send_message(
        self,
        chat_id: UUID,
        sender_id: UUID,
        content: str,
        idempotency_key: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Message:
        """Send a message to a chat with full business logic validation."""
        logger.info(f"Sending message to chat {chat_id} from user {sender_id}")

        # Business rule: Validate message content
        self._validate_message_content(content)

        # Business rule: Check if chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError("Chat not found")

        # Business rule: Check if sender is a member of the chat
        if not self.chat_repo.is_member(chat_id, sender_id, session=session):
            raise ValueError("User is not a member of this chat")

        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = f"{sender_id}:{chat_id}:{datetime.utcnow().isoformat()}"

        # Create the message (repository handles idempotency)
        message = self.message_repo.create_message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            idempotency_key=idempotency_key,
            session=session,
        )

        logger.info(
            f"Created message: {message.id} in chat {chat_id} from user {sender_id}"
        )
        return message

    def get_chat_history(
        self,
        chat_id: UUID,
        user_id: UUID,
        after_timestamp: Optional[datetime] = None,
        limit: int = 50,
        session: Optional[Session] = None,
    ) -> List[Message]:
        """Get chat message history with authorization checks."""
        logger.info(f"Getting chat history for chat {chat_id}, user {user_id}")

        # Business rule: Check if user is a member of the chat
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError("User is not a member of this chat")

        # Business rule: Check if chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError("Chat not found")

        # Business rule: Validate limit
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # Get the message history
        messages = self.message_repo.get_chat_history(
            chat_id=chat_id,
            after_timestamp=after_timestamp,
            limit=limit,
            session=session,
        )

        logger.info(f"Retrieved {len(messages)} messages for chat {chat_id}")
        return messages

    def get_chat_history_before(
        self,
        chat_id: UUID,
        user_id: UUID,
        before_timestamp: datetime,
        limit: int = 50,
        session: Optional[Session] = None,
    ) -> List[Message]:
        """Get chat message history before a timestamp with authorization checks."""
        logger.info(
            f"Getting chat history before {before_timestamp} for chat {chat_id}, user {user_id}"
        )

        # Business rule: Check if user is a member of the chat
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError("User is not a member of this chat")

        # Business rule: Check if chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError("Chat not found")

        # Business rule: Validate limit
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # Get the message history
        messages = self.message_repo.get_chat_history_before(
            chat_id=chat_id,
            before_timestamp=before_timestamp,
            limit=limit,
            session=session,
        )

        logger.info(
            f"Retrieved {len(messages)} messages before {before_timestamp} for chat {chat_id}"
        )
        return messages

    def get_message_by_id(
        self,
        message_id: UUID,
        user_id: UUID,
        session: Optional[Session] = None,
    ) -> Optional[Message]:
        """Get a specific message by ID with authorization checks."""
        logger.info(f"Getting message {message_id} for user {user_id}")

        # Get the message
        message = self.message_repo.get_message_by_id(message_id, session=session)
        if not message:
            return None

        # Business rule: Check if user is a member of the chat
        if not self.chat_repo.is_member(
            cast(UUID, message.chat_id), user_id, session=session
        ):
            raise ValueError("User is not a member of this chat")

        logger.info(f"Retrieved message {message_id} for user {user_id}")
        return message

    def get_recent_messages(
        self,
        chat_id: UUID,
        user_id: UUID,
        limit: int = 50,
        session: Optional[Session] = None,
    ) -> List[Message]:
        """Get recent messages from a chat with authorization checks."""
        logger.info(f"Getting recent messages for chat {chat_id}, user {user_id}")

        # Business rule: Check if user is a member of the chat
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError("User is not a member of this chat")

        # Business rule: Check if chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError("Chat not found")

        # Business rule: Validate limit
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # Get the recent messages
        messages = self.message_repo.get_recent_messages(
            chat_id=chat_id,
            limit=limit,
            session=session,
        )

        logger.info(f"Retrieved {len(messages)} recent messages for chat {chat_id}")
        return messages

    def _validate_message_content(self, content: str) -> None:
        """Validate message content according to business rules."""
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty or only whitespace")

        if len(content) < MIN_MESSAGE_LENGTH:
            raise ValueError(
                f"Message content must be at least {MIN_MESSAGE_LENGTH} character"
            )

        if len(content) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message content cannot exceed {MAX_MESSAGE_LENGTH} characters"
            )

        # Additional validation: check for only whitespace
        if not content.strip():
            raise ValueError("Message content cannot be only whitespace")
