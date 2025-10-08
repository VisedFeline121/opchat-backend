"""Tests for ChatService."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.enums import MemberRole
from app.models.chat import DirectMessage, GroupChat
from app.models.membership import Membership
from app.models.user import User, UserStatus
from app.services.chat_service import (
    ChatService,
    MAX_GROUP_CHAT_MEMBERS,
    MAX_GROUP_CHAT_TOPIC_LENGTH,
)


class TestChatService:
    """Test cases for ChatService."""

    def test_create_direct_message_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test successful direct message creation."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)

        assert isinstance(dm, DirectMessage)
        assert dm.id is not None
        assert dm.dm_key == DirectMessage.create_dm_key(alice.id, bob.id)

        # Verify memberships were created
        members = chat_service.get_chat_members(dm.id, session=test_session)
        assert len(members) == 2
        member_ids = {m.user_id for m in members}
        assert alice.id in member_ids
        assert bob.id in member_ids

    def test_create_direct_message_users_not_exist(
        self, chat_service: ChatService, test_session
    ):
        """Test DM creation with non-existent users."""
        fake_user1 = uuid4()
        fake_user2 = uuid4()

        with pytest.raises(ValueError, match="Users not found"):
            chat_service.create_direct_message(
                fake_user1, fake_user2, session=test_session
            )

    def test_create_direct_message_self_dm_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that creating DM with yourself raises an error."""
        alice = sample_users[0]

        with pytest.raises(
            ValueError, match="Cannot create direct message with yourself"
        ):
            chat_service.create_direct_message(alice.id, alice.id, session=test_session)

    def test_create_group_chat_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test successful group chat creation."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id, charlie.id], session=test_session
        )

        assert isinstance(group, GroupChat)
        assert group.id is not None
        assert group.topic == "Test Group"

        # Verify memberships were created
        members = chat_service.get_chat_members(group.id, session=test_session)
        assert len(members) == 3
        member_ids = {m.user_id for m in members}
        assert alice.id in member_ids
        assert bob.id in member_ids
        assert charlie.id in member_ids

        # Verify alice is admin
        alice_role = chat_service.get_user_role_in_chat(
            group.id, alice.id, session=test_session
        )
        assert alice_role == MemberRole.ADMIN

    def test_create_group_chat_empty_topic_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that creating group chat with empty topic raises an error."""
        alice, bob = sample_users[0], sample_users[1]

        with pytest.raises(ValueError, match="Group chat topic cannot be empty"):
            chat_service.create_group_chat(alice.id, "", [bob.id], session=test_session)

    def test_create_group_chat_whitespace_topic_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that creating group chat with whitespace-only topic raises an error."""
        alice, bob = sample_users[0], sample_users[1]

        with pytest.raises(ValueError, match="Group chat topic cannot be empty"):
            chat_service.create_group_chat(
                alice.id, "   ", [bob.id], session=test_session
            )

    def test_create_group_chat_topic_too_long_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that creating group chat with topic too long raises an error."""
        alice, bob = sample_users[0], sample_users[1]
        long_topic = "a" * 256  # Exceeds MAX_GROUP_CHAT_TOPIC_LENGTH

        with pytest.raises(
            ValueError,
            match=f"Group chat topic cannot exceed {MAX_GROUP_CHAT_TOPIC_LENGTH} characters",
        ):
            chat_service.create_group_chat(
                alice.id, long_topic, [bob.id], session=test_session
            )

    def test_create_group_chat_too_few_members_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that creating group chat with too few members raises an error."""
        alice = sample_users[0]

        with pytest.raises(ValueError, match="Group chat must have at least 2 members"):
            chat_service.create_group_chat(
                alice.id, "Test Group", [], session=test_session
            )

    def test_create_group_chat_creator_not_exist(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test group chat creation with non-existent creator."""
        fake_creator = uuid4()
        bob = sample_users[1]

        with pytest.raises(ValueError, match="Users not found"):
            chat_service.create_group_chat(
                fake_creator, "Test Group", [bob.id], session=test_session
            )

    def test_create_group_chat_members_not_exist(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test group chat creation with non-existent members."""
        alice = sample_users[0]
        fake_member = uuid4()

        with pytest.raises(ValueError, match="Users not found"):
            chat_service.create_group_chat(
                alice.id, "Test Group", [fake_member], session=test_session
            )

    def test_get_user_chats(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test getting user chats."""
        alice, bob = sample_users[0], sample_users[1]

        # Create a DM
        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)

        # Get alice's chats
        alice_chats = chat_service.get_user_chats(alice.id, session=test_session)
        assert len(alice_chats) == 1
        assert alice_chats[0].id == dm.id

        # Get bob's chats
        bob_chats = chat_service.get_user_chats(bob.id, session=test_session)
        assert len(bob_chats) == 1
        assert bob_chats[0].id == dm.id

    def test_get_chat_by_id_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test getting chat by ID."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)
        retrieved_chat = chat_service.get_chat_by_id(dm.id, session=test_session)

        assert retrieved_chat is not None
        assert retrieved_chat.id == dm.id
        assert isinstance(retrieved_chat, DirectMessage)

    def test_get_chat_by_id_not_found(self, chat_service: ChatService, test_session):
        """Test getting non-existent chat by ID."""
        fake_chat_id = uuid4()
        retrieved_chat = chat_service.get_chat_by_id(fake_chat_id, session=test_session)

        assert retrieved_chat is None

    def test_get_chat_members(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test getting chat members."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id, charlie.id], session=test_session
        )

        members = chat_service.get_chat_members(group.id, session=test_session)
        assert len(members) == 3

        member_ids = {m.user_id for m in members}
        assert alice.id in member_ids
        assert bob.id in member_ids
        assert charlie.id in member_ids

    def test_add_member_to_chat_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test adding member to group chat."""
        alice, bob, charlie = sample_users

        # Create group with alice and bob
        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Add charlie
        membership = chat_service.add_member_to_chat(
            group.id, charlie.id, alice.id, session=test_session
        )

        assert membership.user_id == charlie.id
        assert membership.role == MemberRole.MEMBER

        # Verify charlie is now a member
        members = chat_service.get_chat_members(group.id, session=test_session)
        assert len(members) == 3

    def test_add_member_to_dm_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that adding members to DM raises an error."""
        alice, bob, charlie = sample_users

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)

        with pytest.raises(ValueError, match="Cannot add members to direct messages"):
            chat_service.add_member_to_chat(
                dm.id, charlie.id, alice.id, session=test_session
            )

    def test_add_member_to_self_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that adding yourself to a chat raises an error."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        with pytest.raises(ValueError, match="Users cannot add themselves to a chat"):
            chat_service.add_member_to_chat(
                group.id, alice.id, alice.id, session=test_session
            )

    def test_add_member_not_authorized(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test adding member without authorization."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Try to add charlie by bob (not admin)
        with pytest.raises(ValueError, match="User .* does not have admin rights"):
            chat_service.add_member_to_chat(
                group.id, charlie.id, bob.id, session=test_session
            )

    def test_add_member_chat_not_found(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test adding member to non-existent chat."""
        alice, charlie = sample_users[0], sample_users[2]
        fake_chat_id = uuid4()

        with pytest.raises(ValueError, match="Chat .* not found"):
            chat_service.add_member_to_chat(
                fake_chat_id, charlie.id, alice.id, session=test_session
            )

    def test_add_member_user_not_exist(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test adding non-existent user to chat."""
        alice, bob = sample_users[0], sample_users[1]
        fake_user_id = uuid4()

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        with pytest.raises(ValueError, match="Users not found"):
            chat_service.add_member_to_chat(
                group.id, fake_user_id, alice.id, session=test_session
            )

    def test_remove_member_from_chat_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test removing member from group chat."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id, charlie.id], session=test_session
        )

        # Remove charlie
        chat_service.remove_member_from_chat(
            group.id, charlie.id, alice.id, session=test_session
        )

        # Verify charlie is no longer a member
        members = chat_service.get_chat_members(group.id, session=test_session)
        assert len(members) == 2
        member_ids = {m.user_id for m in members}
        assert charlie.id not in member_ids

    def test_remove_member_self_removal(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test user removing themselves from chat."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Bob removes himself
        chat_service.remove_member_from_chat(
            group.id, bob.id, bob.id, session=test_session
        )

        # Verify bob is no longer a member
        members = chat_service.get_chat_members(group.id, session=test_session)
        assert len(members) == 1
        assert members[0].user_id == alice.id

    def test_remove_member_dm_self_only(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that users can only remove themselves from DMs."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)

        # Alice tries to remove bob
        with pytest.raises(
            ValueError, match="Users can only remove themselves from direct messages"
        ):
            chat_service.remove_member_from_chat(
                dm.id, bob.id, alice.id, session=test_session
            )

        # Alice can remove herself
        chat_service.remove_member_from_chat(
            dm.id, alice.id, alice.id, session=test_session
        )

        # Verify alice is no longer a member
        members = chat_service.get_chat_members(dm.id, session=test_session)
        assert len(members) == 1
        assert members[0].user_id == bob.id

    def test_remove_last_admin_raises_error(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that removing the last admin raises an error."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Try to remove alice (the only admin)
        with pytest.raises(
            ValueError, match="Cannot remove the last admin from a group chat"
        ):
            chat_service.remove_member_from_chat(
                group.id, alice.id, alice.id, session=test_session
            )

    def test_is_user_member_of_chat(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test checking if user is member of chat."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Check members
        assert (
            chat_service.is_user_member_of_chat(
                group.id, alice.id, session=test_session
            )
            is True
        )
        assert (
            chat_service.is_user_member_of_chat(group.id, bob.id, session=test_session)
            is True
        )
        assert (
            chat_service.is_user_member_of_chat(
                group.id, charlie.id, session=test_session
            )
            is False
        )

    def test_get_user_role_in_chat(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test getting user role in chat."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Check roles
        alice_role = chat_service.get_user_role_in_chat(
            group.id, alice.id, session=test_session
        )
        bob_role = chat_service.get_user_role_in_chat(
            group.id, bob.id, session=test_session
        )

        assert alice_role == MemberRole.ADMIN
        assert bob_role == MemberRole.MEMBER

    def test_promote_member_to_admin_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test promoting a member to admin."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Add charlie as member
        chat_service.add_member_to_chat(
            group.id, charlie.id, alice.id, session=test_session
        )

        # Promote charlie to admin
        membership = chat_service.promote_member_to_admin(
            group.id, charlie.id, alice.id, session=test_session
        )

        assert membership.role == MemberRole.ADMIN
        assert (
            chat_service.get_user_role_in_chat(
                group.id, charlie.id, session=test_session
            )
            == MemberRole.ADMIN
        )

    def test_demote_admin_to_member_success(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test demoting an admin to member."""
        alice, bob, charlie = sample_users

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        # Promote bob to admin
        chat_service.promote_member_to_admin(
            group.id, bob.id, alice.id, session=test_session
        )

        # Demote bob back to member
        membership = chat_service.demote_admin_to_member(
            group.id, bob.id, alice.id, session=test_session
        )

        assert membership.role == MemberRole.MEMBER
        assert (
            chat_service.get_user_role_in_chat(group.id, bob.id, session=test_session)
            == MemberRole.MEMBER
        )

    def test_get_chat_owner_dm_returns_none(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that DM has no owner."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)
        owner = chat_service.get_chat_owner(dm.id, session=test_session)

        assert owner is None

    def test_get_chat_owner_group_returns_creator(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that group chat owner is the creator."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        owner = chat_service.get_chat_owner(group.id, session=test_session)
        assert owner == alice.id

    def test_is_user_chat_owner_dm_returns_false(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that no user is owner of DM."""
        alice, bob = sample_users[0], sample_users[1]

        dm = chat_service.create_direct_message(alice.id, bob.id, session=test_session)
        is_owner = chat_service.is_user_chat_owner(
            dm.id, alice.id, session=test_session
        )

        assert is_owner is False

    def test_is_user_chat_owner_group_creator_returns_true(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that group chat creator is owner."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        is_owner = chat_service.is_user_chat_owner(
            group.id, alice.id, session=test_session
        )
        assert is_owner is True

    def test_is_user_chat_owner_group_member_returns_false(
        self, chat_service: ChatService, sample_users, test_session
    ):
        """Test that group chat member is not owner."""
        alice, bob = sample_users[0], sample_users[1]

        group = chat_service.create_group_chat(
            alice.id, "Test Group", [bob.id], session=test_session
        )

        is_owner = chat_service.is_user_chat_owner(
            group.id, bob.id, session=test_session
        )
        assert is_owner is False
