"""Tests for MessageRepo."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.models.message import Message


class TestMessageRepo:
    """Test cases for MessageRepo."""

    def test_create_message(self, message_repo, sample_dm, sample_users, clean_db):
        """Test basic message creation."""
        alice = sample_users[0]
        content = "Hello, world!"
        idempotency_key = "test_key_123"

        message = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content=content,
            idempotency_key=idempotency_key,
        )

        assert message.id is not None
        assert message.chat_id == sample_dm.id
        assert message.sender_id == alice.id
        assert message.content == content
        assert message.idempotency_key == idempotency_key
        assert message.created_at is not None

    def test_create_message_duplicate_idempotency(
        self, message_repo, sample_dm, sample_users, clean_db
    ):
        """Test that duplicate idempotency key returns existing message."""
        alice = sample_users[0]
        idempotency_key = "duplicate_test_key"

        # Create first message
        message1 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="First message",
            idempotency_key=idempotency_key,
        )

        # Try to create with same idempotency key
        message2 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="Second message",  # Different content
            idempotency_key=idempotency_key,  # Same key
        )

        # Should return the same message
        assert message1.id == message2.id
        assert message2.content == "First message"  # Original content preserved

    def test_get_by_idempotency_key(self, message_repo, sample_messages):
        """Test retrieving message by idempotency key."""
        original_message = sample_messages[0]

        retrieved = message_repo.get_by_idempotency_key(
            original_message.idempotency_key
        )

        assert retrieved is not None
        assert retrieved.id == original_message.id
        assert retrieved.content == original_message.content

    def test_get_by_idempotency_key_not_found(self, message_repo, clean_db):
        """Test that non-existent idempotency key returns None."""
        result = message_repo.get_by_idempotency_key("nonexistent_key")

        assert result is None

    def test_get_message_by_id(self, message_repo, sample_messages):
        """Test retrieving message by ID."""
        original_message = sample_messages[0]

        retrieved = message_repo.get_message_by_id(original_message.id)

        assert retrieved is not None
        assert retrieved.id == original_message.id
        assert retrieved.content == original_message.content

    def test_get_message_by_id_not_found(self, message_repo, clean_db):
        """Test that non-existent message ID returns None."""
        non_existent_id = uuid4()

        result = message_repo.get_message_by_id(non_existent_id)

        assert result is None

    def test_get_chat_history_all(self, message_repo, sample_messages):
        """Test getting all messages in chronological order."""
        chat_id = sample_messages[0].chat_id

        messages = message_repo.get_chat_history(chat_id, limit=100)

        assert len(messages) == len(sample_messages)
        # Should be in ascending order (oldest first)
        for i in range(1, len(messages)):
            assert messages[i - 1].created_at <= messages[i].created_at

    def test_get_chat_history_with_limit(self, message_repo, sample_messages):
        """Test that limit parameter is respected."""
        chat_id = sample_messages[0].chat_id
        limit = 3

        messages = message_repo.get_chat_history(chat_id, limit=limit)

        assert len(messages) == limit

    def test_get_chat_history_after_timestamp(self, message_repo, sample_messages):
        """Test forward pagination with after_timestamp."""
        chat_id = sample_messages[0].chat_id
        # Use timestamp of second message
        after_timestamp = sample_messages[1].created_at

        messages = message_repo.get_chat_history(
            chat_id, after_timestamp=after_timestamp
        )

        # Should only get messages after the timestamp
        assert len(messages) == len(sample_messages) - 2  # Excludes first 2 messages
        for message in messages:
            assert message.created_at > after_timestamp

    def test_get_chat_history_empty_chat(self, message_repo, sample_dm, clean_db):
        """Test getting history from chat with no messages."""
        messages = message_repo.get_chat_history(sample_dm.id)

        assert messages == []

    def test_get_recent_messages(self, message_repo, sample_messages):
        """Test getting most recent messages in DESC order."""
        chat_id = sample_messages[0].chat_id

        messages = message_repo.get_recent_messages(chat_id, limit=3)

        assert len(messages) == 3
        # Should be in descending order (newest first)
        for i in range(1, len(messages)):
            assert messages[i - 1].created_at >= messages[i].created_at

    def test_get_chat_history_before(self, message_repo, sample_messages):
        """Test backward pagination with before_timestamp."""
        chat_id = sample_messages[0].chat_id
        # Use timestamp of fourth message (index 3)
        before_timestamp = sample_messages[3].created_at

        messages = message_repo.get_chat_history_before(
            chat_id, before_timestamp, limit=2
        )

        # Should get 2 messages before the timestamp
        assert len(messages) == 2
        for message in messages:
            assert message.created_at < before_timestamp

        # Should be in DESC order (most recent first)
        assert messages[0].created_at >= messages[1].created_at

    def test_pagination_no_overlap(self, message_repo, sample_messages):
        """Test that forward and backward pagination don't overlap."""
        chat_id = sample_messages[0].chat_id
        middle_timestamp = sample_messages[2].created_at  # Third message

        # Get messages after middle timestamp (forward)
        after_messages = message_repo.get_chat_history(
            chat_id, after_timestamp=middle_timestamp
        )

        # Get messages before middle timestamp (backward)
        before_messages = message_repo.get_chat_history_before(
            chat_id, before_timestamp=middle_timestamp
        )

        # No message should appear in both results
        after_ids = {msg.id for msg in after_messages}
        before_ids = {msg.id for msg in before_messages}
        middle_id = sample_messages[2].id

        assert len(after_ids.intersection(before_ids)) == 0
        assert middle_id not in after_ids
        assert middle_id not in before_ids

    def test_pagination_deterministic(self, message_repo, sample_messages):
        """Test that same pagination query returns same results."""
        chat_id = sample_messages[0].chat_id
        timestamp = sample_messages[1].created_at

        # Run same query twice
        messages1 = message_repo.get_chat_history(
            chat_id, after_timestamp=timestamp, limit=2
        )
        messages2 = message_repo.get_chat_history(
            chat_id, after_timestamp=timestamp, limit=2
        )

        # Should be identical
        assert len(messages1) == len(messages2)
        for msg1, msg2 in zip(messages1, messages2):
            assert msg1.id == msg2.id
            assert msg1.created_at == msg2.created_at

    def test_pagination_boundary_conditions(self, message_repo, sample_messages):
        """Test pagination at boundaries (first/last messages)."""
        chat_id = sample_messages[0].chat_id

        # Test before first message (should return empty)
        first_timestamp = sample_messages[0].created_at
        before_first = message_repo.get_chat_history_before(
            chat_id, before_timestamp=first_timestamp
        )
        assert before_first == []

        # Test after last message (should return empty)
        last_timestamp = sample_messages[-1].created_at
        after_last = message_repo.get_chat_history(
            chat_id, after_timestamp=last_timestamp
        )
        assert after_last == []

    def test_create_message_coordinated_mode(
        self, message_repo, test_session, sample_dm, sample_users, clean_db
    ):
        """Test message creation in coordinated transaction mode."""
        alice = sample_users[0]

        message = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="Coordinated message",
            idempotency_key="coord_key_123",
            session=test_session,
        )

        # Message should exist in session but not committed
        assert message.content == "Coordinated message"

        # Commit external session
        test_session.commit()

        # Now should be retrievable
        retrieved = message_repo.get_by_idempotency_key("coord_key_123")
        assert retrieved is not None
        assert retrieved.content == "Coordinated message"
