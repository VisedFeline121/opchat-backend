"""Tests for new ChatRepo methods."""

from uuid import uuid4

import pytest

from app.models.membership import MemberRole


class TestChatRepoNewMethods:
    """Test cases for new ChatRepo methods."""

    def test_validate_users_exist_success(self, chat_repo, sample_users, clean_db):
        """Test successful user validation."""
        user_ids = [user.id for user in sample_users]

        result = chat_repo.validate_users_exist(user_ids)

        assert result == user_ids

    def test_validate_users_exist_missing_users(
        self, chat_repo, sample_users, clean_db
    ):
        """Test user validation with missing users."""
        user_ids = [user.id for user in sample_users]
        fake_user = uuid4()
        user_ids.append(fake_user)

        with pytest.raises(ValueError, match="Users not found"):
            chat_repo.validate_users_exist(user_ids)

    def test_validate_users_exist_empty_list(self, chat_repo, clean_db):
        """Test user validation with empty list."""
        result = chat_repo.validate_users_exist([])

        assert result == []

    def test_is_group_chat_true(self, chat_repo, sample_group_chat):
        """Test group chat identification returns True."""
        is_group = chat_repo.is_group_chat(sample_group_chat.id)

        assert is_group is True

    def test_is_group_chat_false(self, chat_repo, sample_dm):
        """Test group chat identification returns False for DM."""
        is_group = chat_repo.is_group_chat(sample_dm.id)

        assert is_group is False

    def test_is_group_chat_nonexistent(self, chat_repo, clean_db):
        """Test group chat identification for non-existent chat."""
        fake_id = uuid4()

        is_group = chat_repo.is_group_chat(fake_id)

        assert is_group is False

    def test_is_direct_message_true(self, chat_repo, sample_dm):
        """Test direct message identification returns True."""
        is_dm = chat_repo.is_direct_message(sample_dm.id)

        assert is_dm is True

    def test_is_direct_message_false(self, chat_repo, sample_group_chat):
        """Test direct message identification returns False for group chat."""
        is_dm = chat_repo.is_direct_message(sample_group_chat.id)

        assert is_dm is False

    def test_is_direct_message_nonexistent(self, chat_repo, clean_db):
        """Test direct message identification for non-existent chat."""
        fake_id = uuid4()

        is_dm = chat_repo.is_direct_message(fake_id)

        assert is_dm is False

    def test_get_user_role_in_chat_admin(
        self, chat_repo, sample_group_chat, sample_users
    ):
        """Test getting admin role in chat."""
        alice = sample_users[0]  # Admin

        role = chat_repo.get_user_role_in_chat(sample_group_chat.id, alice.id)

        assert role == MemberRole.ADMIN

    def test_get_user_role_in_chat_member(
        self, chat_repo, sample_group_chat, sample_users
    ):
        """Test getting member role in chat."""
        bob = sample_users[1]  # Member

        role = chat_repo.get_user_role_in_chat(sample_group_chat.id, bob.id)

        assert role == MemberRole.MEMBER

    def test_get_user_role_in_chat_nonexistent(self, chat_repo, clean_db):
        """Test getting role for non-existent chat."""
        fake_chat_id = uuid4()
        fake_user_id = uuid4()

        role = chat_repo.get_user_role_in_chat(fake_chat_id, fake_user_id)

        assert role is None

    def test_get_user_role_in_chat_not_member(
        self, chat_repo, sample_group_chat, clean_db
    ):
        """Test getting role for user not in chat."""
        fake_user_id = uuid4()

        role = chat_repo.get_user_role_in_chat(sample_group_chat.id, fake_user_id)

        assert role is None

    def test_get_chat_with_members(self, chat_repo, sample_group_chat):
        """Test getting chat with members loaded."""
        chat = chat_repo.get_chat_with_members(sample_group_chat.id)

        assert chat is not None
        assert chat.id == sample_group_chat.id
        assert chat.type == "group"
        # Members should be accessible via relationship
        assert hasattr(chat, "memberships")
        assert len(chat.memberships) == 3

    def test_get_chat_with_members_not_found(self, chat_repo, clean_db):
        """Test getting non-existent chat with members."""
        fake_id = uuid4()

        chat = chat_repo.get_chat_with_members(fake_id)

        assert chat is None
