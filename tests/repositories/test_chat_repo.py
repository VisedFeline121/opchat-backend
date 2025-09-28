"""Tests for ChatRepo."""

from uuid import uuid4

import pytest

from app.models.chat import DirectMessage, GroupChat
from app.models.membership import MemberRole


class TestChatRepo:
    """Test cases for ChatRepo."""

    def test_create_dm_new(self, chat_repo, sample_users, clean_db):
        """Test creating a new direct message."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_repo.create_direct_message(alice.id, bob.id)

        assert isinstance(dm, DirectMessage)
        assert dm.id is not None
        assert dm.dm_key == DirectMessage.create_dm_key(alice.id, bob.id)

        # Verify memberships were created
        members = chat_repo.get_chat_members(dm.id)
        assert len(members) == 2

        member_ids = {m.user_id for m in members}
        assert alice.id in member_ids
        assert bob.id in member_ids

        # Both should be regular members
        for membership in members:
            assert membership.role == MemberRole.MEMBER

    def test_create_dm_existing(self, chat_repo, sample_dm, sample_users):
        """Test that creating existing DM returns the same DM."""
        alice, bob = sample_users[0], sample_users[1]

        # Try to create DM that already exists
        dm = chat_repo.create_direct_message(alice.id, bob.id)

        # Should return the existing DM
        assert dm.id == sample_dm.id
        assert dm.dm_key == sample_dm.dm_key

    def test_create_dm_same_user_error(self, chat_repo, sample_users, clean_db):
        """Test that creating DM with same user raises ValueError."""
        alice = sample_users[0]

        with pytest.raises(
            ValueError, match="Cannot create direct message with the same user"
        ):
            chat_repo.create_direct_message(alice.id, alice.id)

    def test_create_dm_uses_dm_key(self, chat_repo, sample_users, clean_db):
        """Test that DM key is generated correctly."""
        alice, bob = sample_users[0], sample_users[1]

        # Create DM in both directions - should use same key
        expected_key = DirectMessage.create_dm_key(alice.id, bob.id)

        dm1 = chat_repo.create_direct_message(alice.id, bob.id)
        dm2 = chat_repo.create_direct_message(bob.id, alice.id)  # Reversed order

        assert dm1.id == dm2.id  # Should be the same DM
        assert dm1.dm_key == expected_key
        assert dm2.dm_key == expected_key

    def test_create_group_chat(self, chat_repo, sample_users, clean_db):
        """Test creating a group chat with members."""
        alice, bob, charlie = sample_users
        topic = "Test Group Chat"
        member_ids = [bob.id, charlie.id]

        group = chat_repo.create_group_chat(alice.id, topic, member_ids)

        assert isinstance(group, GroupChat)
        assert group.id is not None
        assert group.topic == topic

        # Verify memberships
        members = chat_repo.get_chat_members(group.id)
        assert len(members) == 3  # Creator + 2 members

        # Find creator membership
        creator_membership = next(m for m in members if m.user_id == alice.id)
        assert creator_membership.role == MemberRole.ADMIN

        # Other members should be regular members
        other_members = [m for m in members if m.user_id != alice.id]
        assert len(other_members) == 2
        for membership in other_members:
            assert membership.role == MemberRole.MEMBER
            assert membership.user_id in [bob.id, charlie.id]

    def test_create_group_chat_creator_in_members(
        self, chat_repo, sample_users, clean_db
    ):
        """Test group creation when creator is included in member_ids."""
        alice, bob, charlie = sample_users
        # Include creator in member list
        member_ids = [alice.id, bob.id, charlie.id]

        group = chat_repo.create_group_chat(alice.id, "Test Group", member_ids)

        # Should still only have 3 members (no duplicate)
        members = chat_repo.get_chat_members(group.id)
        assert len(members) == 3

        # Creator should still be admin
        creator_membership = next(m for m in members if m.user_id == alice.id)
        assert creator_membership.role == MemberRole.ADMIN

    def test_create_group_chat_empty_members(self, chat_repo, sample_users, clean_db):
        """Test group creation with empty member list."""
        alice = sample_users[0]

        group = chat_repo.create_group_chat(alice.id, "Solo Group", [])

        # Should have just the creator
        members = chat_repo.get_chat_members(group.id)
        assert len(members) == 1
        assert members[0].user_id == alice.id
        assert members[0].role == MemberRole.ADMIN

    def test_get_user_chats(
        self, chat_repo, sample_dm, sample_group_chat, sample_users
    ):
        """Test retrieving all chats for a user."""
        alice = sample_users[0]

        chats = chat_repo.get_user_chats(alice.id)

        # Alice should be in both the DM and group chat
        assert len(chats) >= 2
        chat_ids = {chat.id for chat in chats}
        assert sample_dm.id in chat_ids
        assert sample_group_chat.id in chat_ids

    def test_get_user_chats_empty(self, chat_repo, clean_db):
        """Test get_user_chats for user with no chats."""
        non_member_id = uuid4()

        chats = chat_repo.get_user_chats(non_member_id)

        assert chats == []

    def test_add_member_new(self, chat_repo, sample_group_chat, user_repo, clean_db):
        """Test adding a new member to a chat."""
        # Create a real user first
        new_user = user_repo.create_user("newmember", "hash123")

        membership = chat_repo.add_member(
            sample_group_chat.id, new_user.id, MemberRole.MEMBER
        )

        assert membership.chat_id == sample_group_chat.id
        assert membership.user_id == new_user.id
        assert membership.role == MemberRole.MEMBER

        # Verify member was added
        assert chat_repo.is_member(sample_group_chat.id, new_user.id) is True

    def test_add_member_existing_same_role(
        self, chat_repo, sample_group_chat, sample_users
    ):
        """Test adding existing member with same role returns existing membership."""
        bob = sample_users[1]  # Already a member

        membership = chat_repo.add_member(
            sample_group_chat.id, bob.id, MemberRole.MEMBER
        )

        # Should return existing membership
        assert membership.user_id == bob.id
        assert membership.role == MemberRole.MEMBER

    def test_add_member_existing_different_role(
        self, chat_repo, sample_group_chat, sample_users
    ):
        """Test adding existing member with different role updates the role."""
        bob = sample_users[1]  # Currently a MEMBER

        membership = chat_repo.add_member(
            sample_group_chat.id, bob.id, MemberRole.ADMIN
        )

        # Should update role to ADMIN
        assert membership.user_id == bob.id
        assert membership.role == MemberRole.ADMIN

    def test_remove_member(self, chat_repo, sample_group_chat, sample_users):
        """Test removing a member from a chat."""
        bob = sample_users[1]

        # Verify bob is initially a member
        assert chat_repo.is_member(sample_group_chat.id, bob.id) is True

        chat_repo.remove_member(sample_group_chat.id, bob.id)

        # Verify bob is no longer a member
        assert chat_repo.is_member(sample_group_chat.id, bob.id) is False

    def test_remove_member_not_found(self, chat_repo, sample_group_chat, clean_db):
        """Test removing non-existent member doesn't raise error."""
        non_member_id = uuid4()

        # Should not raise exception
        chat_repo.remove_member(sample_group_chat.id, non_member_id)

    def test_is_member_true(self, chat_repo, sample_group_chat, sample_users):
        """Test is_member returns True for existing member."""
        alice = sample_users[0]  # Admin of the group

        is_member = chat_repo.is_member(sample_group_chat.id, alice.id)

        assert is_member is True

    def test_is_member_false(self, chat_repo, sample_group_chat, clean_db):
        """Test is_member returns False for non-member."""
        non_member_id = uuid4()

        is_member = chat_repo.is_member(sample_group_chat.id, non_member_id)

        assert is_member is False

    def test_get_chat_by_id(self, chat_repo, sample_dm):
        """Test retrieving chat by ID."""
        chat = chat_repo.get_chat_by_id(sample_dm.id)

        assert chat is not None
        assert chat.id == sample_dm.id
        assert isinstance(chat, DirectMessage)

    def test_get_chat_by_id_not_found(self, chat_repo, clean_db):
        """Test that non-existent chat ID returns None."""
        non_existent_id = uuid4()

        chat = chat_repo.get_chat_by_id(non_existent_id)

        assert chat is None

    def test_get_chat_members(self, chat_repo, sample_group_chat, sample_users):
        """Test retrieving all members of a chat."""
        members = chat_repo.get_chat_members(sample_group_chat.id)

        assert len(members) == 3  # Alice (admin), Bob, Charlie

        # Verify all expected users are members
        member_user_ids = {m.user_id for m in members}
        expected_user_ids = {user.id for user in sample_users}
        assert member_user_ids == expected_user_ids

        # Verify Alice is admin
        alice_membership = next(m for m in members if m.user_id == sample_users[0].id)
        assert alice_membership.role == MemberRole.ADMIN

    def test_create_dm_coordinated_mode(
        self, chat_repo, test_session, sample_users, clean_db
    ):
        """Test DM creation in coordinated transaction mode."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_repo.create_direct_message(alice.id, bob.id, session=test_session)

        # DM should exist in session
        assert dm.dm_key == DirectMessage.create_dm_key(alice.id, bob.id)

        # Commit external session
        test_session.commit()

        # Now should be retrievable
        retrieved = chat_repo.get_chat_by_id(dm.id)
        assert retrieved is not None
        assert retrieved.id == dm.id

    def test_create_group_coordinated_mode(
        self, chat_repo, test_session, sample_users, clean_db
    ):
        """Test group creation in coordinated transaction mode."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_repo.create_group_chat(
            creator_id=alice.id,
            topic="Coordinated Group",
            member_ids=[bob.id],
            session=test_session,
        )

        # Group should exist in session
        test_session.refresh(group)  # Ensure object is fresh
        assert group.topic == "Coordinated Group"

        # Commit external session
        test_session.commit()

        # Now should be retrievable using the same session
        retrieved = chat_repo.get_chat_by_id(group.id, session=test_session)
        assert retrieved is not None
        assert retrieved.topic == "Coordinated Group"
