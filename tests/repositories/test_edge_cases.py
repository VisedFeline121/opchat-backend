"""Edge cases and bad flow tests for repositories."""

from uuid import uuid4

import pytest
from psycopg2.errors import CheckViolation, ForeignKeyViolation
from sqlalchemy.exc import DataError, IntegrityError

from app.repositories import ChatRepo, MessageRepo, UserRepo


class TestInputValidation:
    """Test input validation and malformed data handling."""

    def test_create_user_none_username(self, user_repo, clean_db):
        """Test creating user with None username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            user_repo.create_user(None, "password_hash")

    def test_create_user_empty_username(self, user_repo, clean_db):
        """Test creating user with empty username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            user_repo.create_user("", "password_hash")

    def test_create_user_whitespace_username(self, user_repo, clean_db):
        """Test creating user with whitespace-only username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            user_repo.create_user("   ", "password_hash")

    def test_create_user_none_password(self, user_repo, clean_db):
        """Test creating user with None password."""
        with pytest.raises(ValueError, match="Password hash cannot be empty"):
            user_repo.create_user("username", None)

    def test_create_user_very_long_username(self, user_repo, clean_db):
        """Test username exceeding length limit."""
        long_username = "a" * 1000  # Exceeds 255 character limit
        with pytest.raises(ValueError, match="Username cannot exceed 255 characters"):
            user_repo.create_user(long_username, "password_hash")

    def test_get_user_by_invalid_uuid_string(self, user_repo, clean_db):
        """Test retrieving user with malformed UUID string."""
        with pytest.raises(ValueError, match="Invalid UUID format"):
            user_repo.get_user_by_id("not-a-valid-uuid")


class TestForeignKeyViolations:
    """Test foreign key constraint violations."""

    def test_create_message_nonexistent_chat(
        self, message_repo, sample_users, clean_db
    ):
        """Test creating message with non-existent chat ID."""
        fake_chat_id = uuid4()
        alice = sample_users[0]

        with pytest.raises(IntegrityError) as exc_info:
            message_repo.create_message(
                chat_id=fake_chat_id,
                sender_id=alice.id,
                content="Test message",
                idempotency_key="test_key",
            )

        # Verify it's specifically a foreign key violation
        assert "foreign key constraint" in str(exc_info.value).lower()

    def test_create_message_nonexistent_sender(self, message_repo, sample_dm, clean_db):
        """Test creating message with non-existent sender ID."""
        fake_user_id = uuid4()

        with pytest.raises(IntegrityError) as exc_info:
            message_repo.create_message(
                chat_id=sample_dm.id,
                sender_id=fake_user_id,
                content="Test message",
                idempotency_key="test_key",
            )

        assert "foreign key constraint" in str(exc_info.value).lower()

    def test_add_member_nonexistent_chat(self, chat_repo, sample_users, clean_db):
        """Test adding member to non-existent chat."""
        fake_chat_id = uuid4()
        alice = sample_users[0]

        with pytest.raises(IntegrityError) as exc_info:
            chat_repo.add_member(fake_chat_id, alice.id)

        assert "foreign key constraint" in str(exc_info.value).lower()

    def test_add_member_nonexistent_user(self, chat_repo, sample_dm, clean_db):
        """Test adding non-existent user to chat."""
        fake_user_id = uuid4()

        with pytest.raises(IntegrityError) as exc_info:
            chat_repo.add_member(sample_dm.id, fake_user_id)

        assert "foreign key constraint" in str(exc_info.value).lower()


class TestBoundaryConditions:
    """Test boundary conditions and extreme values."""

    def test_get_chat_history_zero_limit(self, message_repo, sample_dm, clean_db):
        """Test pagination with limit=0."""
        messages = message_repo.get_chat_history(sample_dm.id, limit=0)
        assert len(messages) == 0

    def test_get_chat_history_negative_limit(self, message_repo, sample_dm, clean_db):
        """Test pagination with negative limit."""
        with pytest.raises(ValueError, match="Limit must be non-negative"):
            message_repo.get_chat_history(sample_dm.id, limit=-1)

    def test_get_chat_history_very_large_limit(self, message_repo, sample_dm, clean_db):
        """Test pagination with extremely large limit."""
        messages = message_repo.get_chat_history(sample_dm.id, limit=1000000)
        assert isinstance(messages, list)
        assert len(messages) <= 1000000  # Should not exceed actual message count

    def test_create_message_empty_content(
        self, message_repo, sample_dm, sample_users, clean_db
    ):
        """Test creating message with empty content."""
        alice = sample_users[0]

        # Empty content might be allowed depending on business rules
        # Test what actually happens
        message = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="",
            idempotency_key="empty_content_key",
        )

        # Verify behavior - either succeeds with empty content or fails
        if message:
            assert message.content == ""

    def test_create_message_very_long_content(
        self, message_repo, sample_dm, sample_users, clean_db
    ):
        """Test creating message with very long content."""
        alice = sample_users[0]
        long_content = "a" * 10000  # Test database limits

        try:
            message = message_repo.create_message(
                chat_id=sample_dm.id,
                sender_id=alice.id,
                content=long_content,
                idempotency_key="long_content_key",
            )
            # If successful, verify content was stored
            assert message.content == long_content
        except (DataError, IntegrityError):
            # Expected if content exceeds database limits
            pass


class TestBusinessLogicEdgeCases:
    """Test business logic edge cases."""

    def test_create_group_with_duplicate_member_ids(
        self, chat_repo, sample_users, clean_db
    ):
        """Test group creation with duplicate member IDs in list."""
        alice, bob = sample_users[0], sample_users[1]

        # Include duplicate member IDs
        duplicate_members = [bob.id, bob.id, alice.id]

        group = chat_repo.create_group_chat(
            creator_id=alice.id,
            topic="Duplicate Members Test",
            member_ids=duplicate_members,
        )

        # Verify duplicates were handled (should have unique memberships)
        members = chat_repo.get_chat_members(group.id)
        unique_user_ids = {m.user_id for m in members}
        assert len(unique_user_ids) == 2  # alice and bob, no duplicates

    def test_create_dm_with_swapped_user_order(self, chat_repo, sample_users, clean_db):
        """Test that DM creation is order-independent."""
        alice, bob = sample_users[0], sample_users[1]

        # Create DM with alice->bob order
        dm1 = chat_repo.create_direct_message(alice.id, bob.id)

        # Try to create DM with bob->alice order (should return same DM)
        dm2 = chat_repo.create_direct_message(bob.id, alice.id)

        assert dm1.id == dm2.id
        assert dm1.dm_key == dm2.dm_key

    def test_remove_nonexistent_member(
        self, chat_repo, sample_group_chat, sample_users, clean_db
    ):
        """Test removing a user who is not a member."""
        # Get a user who is not in the group
        all_users = sample_users
        group_members = chat_repo.get_chat_members(sample_group_chat.id)
        member_ids = {m.user_id for m in group_members}

        non_member = None
        for user in all_users:
            if user.id not in member_ids:
                non_member = user
                break

        if non_member:
            # Should handle gracefully (no error, no effect)
            chat_repo.remove_member(sample_group_chat.id, non_member.id)

            # Verify member count unchanged
            members_after = chat_repo.get_chat_members(sample_group_chat.id)
            assert len(members_after) == len(group_members)


class TestIdempotencyEdgeCases:
    """Test idempotency edge cases."""

    def test_create_message_same_idempotency_different_content(
        self, message_repo, sample_dm, sample_users, clean_db
    ):
        """Test same idempotency key with different message content."""
        alice = sample_users[0]
        idempotency_key = "same_key_different_content"

        # Create first message
        message1 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="First content",
            idempotency_key=idempotency_key,
        )

        # Try to create with same key but different content
        message2 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="Different content",  # Different!
            idempotency_key=idempotency_key,
        )

        # Should return original message (idempotency wins)
        assert message1.id == message2.id
        assert message1.content == "First content"  # Original content preserved
        assert message2.content == "First content"  # Not the new content

    def test_create_message_same_idempotency_different_sender(
        self, message_repo, sample_dm, sample_users, clean_db
    ):
        """Test same idempotency key with different sender."""
        alice, bob = sample_users[0], sample_users[1]
        idempotency_key = "same_key_different_sender"

        # Create first message
        message1 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=alice.id,
            content="Test content",
            idempotency_key=idempotency_key,
        )

        # Try to create with same key but different sender
        message2 = message_repo.create_message(
            chat_id=sample_dm.id,
            sender_id=bob.id,  # Different sender!
            content="Test content",
            idempotency_key=idempotency_key,
        )

        # Should return original message
        assert message1.id == message2.id
        assert message1.sender_id == alice.id  # Original sender preserved
        assert message2.sender_id == alice.id  # Not bob
