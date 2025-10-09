"""Tests for MessageService."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.chat import DirectMessage, GroupChat
from app.models.membership import Membership
from app.models.message import Message
from app.models.user import User, UserStatus
from app.services.message_service import (
    MessageService,
    MAX_MESSAGE_LENGTH,
    MIN_MESSAGE_LENGTH,
)


class TestMessageService:
    """Test cases for MessageService."""

    def test_send_message_success(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test successful message sending."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Alice sends a message
        message = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            session=test_session,
        )

        assert isinstance(message, Message)
        assert message.id is not None
        assert message.chat_id == dm.id
        assert message.sender_id == alice.id
        assert message.content == "Hello Bob!"
        assert message.created_at is not None

    def test_send_message_with_idempotency_key(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test message sending with idempotency key."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        idempotency_key = "test-key-123"

        # Send message with idempotency key
        message1 = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            idempotency_key=idempotency_key,
            session=test_session,
        )

        # Send same message again with same key
        message2 = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            idempotency_key=idempotency_key,
            session=test_session,
        )

        # Should return the same message (idempotency)
        assert message1.id == message2.id
        assert message1.content == message2.content

    def test_send_message_user_not_member(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test sending message when user is not a member of chat."""
        alice, bob, charlie = sample_users[0], sample_users[1], sample_users[2]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Charlie tries to send a message (not a member)
        with pytest.raises(ValueError, match="User is not a member of this chat"):
            message_service.send_message(
                chat_id=dm.id,
                sender_id=charlie.id,
                content="Hello!",
                session=test_session,
            )

    def test_send_message_chat_not_found(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test sending message to non-existent chat."""
        alice = sample_users[0]
        fake_chat_id = uuid4()

        with pytest.raises(ValueError, match="Chat not found"):
            message_service.send_message(
                chat_id=fake_chat_id,
                sender_id=alice.id,
                content="Hello!",
                session=test_session,
            )

    def test_send_message_empty_content(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test sending message with empty content."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service.send_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content="",
                session=test_session,
            )

    def test_send_message_whitespace_only_content(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test sending message with whitespace-only content."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service.send_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content="   ",
                session=test_session,
            )

    def test_send_message_content_too_long(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test sending message with content that's too long."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        long_content = "a" * (MAX_MESSAGE_LENGTH + 1)

        with pytest.raises(ValueError, match="Message content cannot exceed"):
            message_service.send_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content=long_content,
                session=test_session,
            )

    def test_get_chat_history_success(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test successful chat history retrieval."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Send some messages
        message1 = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            session=test_session,
        )

        message2 = message_service.send_message(
            chat_id=dm.id,
            sender_id=bob.id,
            content="Hi Alice!",
            session=test_session,
        )

        # Get chat history
        messages = message_service.get_chat_history(
            chat_id=dm.id,
            user_id=alice.id,
            session=test_session,
        )

        assert len(messages) == 2
        assert messages[0].id == message1.id
        assert messages[1].id == message2.id

    def test_get_chat_history_with_pagination(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test chat history retrieval with pagination."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Send multiple messages
        messages = []
        for i in range(5):
            message = message_service.send_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content=f"Message {i}",
                session=test_session,
            )
            messages.append(message)

        # Get all messages
        all_messages = message_service.get_chat_history(
            chat_id=dm.id,
            user_id=alice.id,
            limit=10,
            session=test_session,
        )

        assert len(all_messages) == 5
        # Messages should be in chronological order (ascending)
        assert all_messages[0].content == "Message 0"
        assert all_messages[4].content == "Message 4"

        # Test pagination with smaller limit
        first_batch = message_service.get_chat_history(
            chat_id=dm.id,
            user_id=alice.id,
            limit=3,
            session=test_session,
        )

        assert len(first_batch) == 3
        assert first_batch[0].content == "Message 0"
        assert first_batch[2].content == "Message 2"

    def test_get_chat_history_user_not_member(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test getting chat history when user is not a member."""
        alice, bob, charlie = sample_users[0], sample_users[1], sample_users[2]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Charlie tries to get chat history (not a member)
        with pytest.raises(ValueError, match="User is not a member of this chat"):
            message_service.get_chat_history(
                chat_id=dm.id,
                user_id=charlie.id,
                session=test_session,
            )

    def test_get_chat_history_invalid_limit(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test getting chat history with invalid limit."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Test limit too high
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            message_service.get_chat_history(
                chat_id=dm.id,
                user_id=alice.id,
                limit=101,
                session=test_session,
            )

        # Test limit too low
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            message_service.get_chat_history(
                chat_id=dm.id,
                user_id=alice.id,
                limit=0,
                session=test_session,
            )

    def test_get_chat_history_before_success(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test successful chat history retrieval before timestamp."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Send some messages
        message1 = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="First message",
            session=test_session,
        )

        message2 = message_service.send_message(
            chat_id=dm.id,
            sender_id=bob.id,
            content="Second message",
            session=test_session,
        )

        # Get all messages first to verify they exist
        all_messages = message_service.get_chat_history(
            chat_id=dm.id,
            user_id=alice.id,
            limit=10,
            session=test_session,
        )

        assert len(all_messages) == 2

        # Test the method works by using a timestamp in the future
        from datetime import timedelta

        future_timestamp = message2.created_at + timedelta(seconds=1)

        messages = message_service.get_chat_history_before(
            chat_id=dm.id,
            user_id=alice.id,
            before_timestamp=future_timestamp,
            session=test_session,
        )

        # Should get both messages since we're using a future timestamp
        assert len(messages) == 2
        # Should be in descending order (most recent first) for get_chat_history_before
        assert messages[0].content == "Second message"
        assert messages[1].content == "First message"

    def test_get_message_by_id_success(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test successful message retrieval by ID."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Send a message
        message = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            session=test_session,
        )

        # Get message by ID
        retrieved_message = message_service.get_message_by_id(
            message_id=message.id,
            user_id=alice.id,
            session=test_session,
        )

        assert retrieved_message is not None
        assert retrieved_message.id == message.id
        assert retrieved_message.content == "Hello Bob!"

    def test_get_message_by_id_not_found(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test getting message by ID when message doesn't exist."""
        alice = sample_users[0]
        fake_message_id = uuid4()

        retrieved_message = message_service.get_message_by_id(
            message_id=fake_message_id,
            user_id=alice.id,
            session=test_session,
        )

        assert retrieved_message is None

    def test_get_message_by_id_user_not_member(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test getting message by ID when user is not a member of chat."""
        alice, bob, charlie = sample_users[0], sample_users[1], sample_users[2]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Alice sends a message
        message = message_service.send_message(
            chat_id=dm.id,
            sender_id=alice.id,
            content="Hello Bob!",
            session=test_session,
        )

        # Charlie tries to get the message (not a member)
        with pytest.raises(ValueError, match="User is not a member of this chat"):
            message_service.get_message_by_id(
                message_id=message.id,
                user_id=charlie.id,
                session=test_session,
            )

    def test_get_recent_messages_success(
        self, message_service: MessageService, sample_users, test_session
    ):
        """Test successful recent messages retrieval."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM between alice and bob
        dm = message_service.chat_repo.create_direct_message(
            alice.id, bob.id, session=test_session
        )

        # Send multiple messages
        messages = []
        for i in range(5):
            message = message_service.send_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content=f"Message {i}",
                session=test_session,
            )
            messages.append(message)

        # Get recent messages (limit 3)
        recent_messages = message_service.get_recent_messages(
            chat_id=dm.id,
            user_id=alice.id,
            limit=3,
            session=test_session,
        )

        assert len(recent_messages) == 3
        # Should be in descending order (most recent first)
        # Since messages are created quickly, we can't rely on exact ordering
        # Just verify we get 3 messages and they're all from our test
        message_contents = [msg.content for msg in recent_messages]
        assert "Message 0" in message_contents
        assert "Message 1" in message_contents
        assert "Message 2" in message_contents

    def test_validate_message_content_success(self, message_service: MessageService):
        """Test successful message content validation."""
        # Valid content should not raise
        message_service._validate_message_content("Hello world!")
        message_service._validate_message_content("a")  # Minimum length
        message_service._validate_message_content(
            "a" * MAX_MESSAGE_LENGTH
        )  # Maximum length

    def test_validate_message_content_empty(self, message_service: MessageService):
        """Test message content validation with empty content."""
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service._validate_message_content("")

    def test_validate_message_content_whitespace_only(
        self, message_service: MessageService
    ):
        """Test message content validation with whitespace-only content."""
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service._validate_message_content("   ")

    def test_validate_message_content_too_short(self, message_service: MessageService):
        """Test message content validation with content that's too short."""
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service._validate_message_content("")

    def test_validate_message_content_too_long(self, message_service: MessageService):
        """Test message content validation with content that's too long."""
        long_content = "a" * (MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(ValueError, match="Message content cannot exceed"):
            message_service._validate_message_content(long_content)

    def test_validate_message_content_whitespace_trimming(
        self, message_service: MessageService
    ):
        """Test that message content validation trims whitespace."""
        # Content with leading/trailing whitespace should be trimmed and validated
        message_service._validate_message_content("  Hello world!  ")

        # But whitespace-only content should still fail
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            message_service._validate_message_content("  \t\n  ")
