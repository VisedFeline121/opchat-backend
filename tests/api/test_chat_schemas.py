"""Tests for chat API schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas.chat import (
    AddMemberRequest,
    ChatResponse,
    ChatType,
    CreateChatRequest,
    MemberRole,
    MembershipResponse,
    UserResponse,
)


class TestChatSchemas:
    """Test cases for chat API schemas."""

    def test_create_chat_request_dm_validation(self):
        """Test CreateChatRequest validation for DM."""
        user1 = uuid4()
        user2 = uuid4()

        request = CreateChatRequest(type=ChatType.DM, participant_ids=[user1, user2])

        assert request.type == ChatType.DM
        assert request.participant_ids == [user1, user2]
        assert request.topic is None

    def test_create_chat_request_group_validation(self):
        """Test CreateChatRequest validation for group chat."""
        user1 = uuid4()
        user2 = uuid4()
        user3 = uuid4()
        topic = "Test Group"

        request = CreateChatRequest(
            type=ChatType.GROUP, participant_ids=[user1, user2, user3], topic=topic
        )

        assert request.type == ChatType.GROUP
        assert request.participant_ids == [user1, user2, user3]
        assert request.topic == topic

    def test_create_chat_request_dm_wrong_participant_count(self):
        """Test CreateChatRequest validation fails for DM with wrong participant count."""
        user1 = uuid4()
        user2 = uuid4()
        user3 = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(
                type=ChatType.DM,
                participant_ids=[user1, user2, user3],  # 3 participants for DM
            )

        assert "Direct messages must have exactly 2 participants" in str(exc_info.value)

    def test_create_chat_request_group_too_few_participants(self):
        """Test CreateChatRequest validation fails for group with too few participants."""
        user1 = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(
                type=ChatType.GROUP,
                participant_ids=[user1],  # Only 1 participant
                topic="Test Group",
            )

        assert "Group chats must have at least 2 participants" in str(exc_info.value)

    def test_create_chat_request_group_missing_topic(self):
        """Test CreateChatRequest validation fails for group without topic."""
        user1 = uuid4()
        user2 = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(
                type=ChatType.GROUP,
                participant_ids=[user1, user2],
                # Missing topic
            )

        assert "Group chats must have a topic" in str(exc_info.value)

    def test_create_chat_request_empty_participants(self):
        """Test CreateChatRequest validation fails with empty participants."""
        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(type=ChatType.DM, participant_ids=[])  # Empty list

        assert "List should have at least 1 item" in str(exc_info.value)

    def test_create_chat_request_topic_too_long(self):
        """Test CreateChatRequest validation fails with topic too long."""
        user1 = uuid4()
        user2 = uuid4()
        long_topic = "x" * 256  # Exceeds max_length=255

        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(
                type=ChatType.GROUP, participant_ids=[user1, user2], topic=long_topic
            )

        assert "String should have at most 255 characters" in str(exc_info.value)

    def test_add_member_request_validation(self):
        """Test AddMemberRequest validation."""
        user_id = uuid4()

        request = AddMemberRequest(user_id=user_id, role=MemberRole.ADMIN)

        assert request.user_id == user_id
        assert request.role == MemberRole.ADMIN

    def test_add_member_request_default_role(self):
        """Test AddMemberRequest defaults to MEMBER role."""
        user_id = uuid4()

        request = AddMemberRequest(user_id=user_id)

        assert request.user_id == user_id
        assert request.role == MemberRole.MEMBER

    def test_chat_response_serialization(self):
        """Test ChatResponse serialization."""
        chat_id = uuid4()
        user_id = uuid4()
        membership_id = uuid4()

        user_response = UserResponse(id=user_id, username="testuser")

        membership_response = MembershipResponse(
            user_id=user_id,
            role=MemberRole.MEMBER,
            joined_at="2023-01-01T00:00:00Z",
            user=user_response,
        )

        chat_response = ChatResponse(
            id=chat_id,
            type=ChatType.DM,
            created_at="2023-01-01T00:00:00Z",
            members=[membership_response],
            dm_key="test-dm-key",
        )

        assert chat_response.id == chat_id
        assert chat_response.type == ChatType.DM
        assert chat_response.dm_key == "test-dm-key"
        assert chat_response.topic is None
        assert len(chat_response.members) == 1
        assert chat_response.members[0].role == MemberRole.MEMBER

    def test_chat_response_group_serialization(self):
        """Test ChatResponse serialization for group chat."""
        chat_id = uuid4()
        user_id = uuid4()

        user_response = UserResponse(id=user_id, username="testuser")

        membership_response = MembershipResponse(
            user_id=user_id,
            role=MemberRole.ADMIN,
            joined_at="2023-01-01T00:00:00Z",
            user=user_response,
        )

        chat_response = ChatResponse(
            id=chat_id,
            type=ChatType.GROUP,
            created_at="2023-01-01T00:00:00Z",
            members=[membership_response],
            topic="Test Group",
        )

        assert chat_response.id == chat_id
        assert chat_response.type == ChatType.GROUP
        assert chat_response.topic == "Test Group"
        assert chat_response.dm_key is None
        assert len(chat_response.members) == 1
        assert chat_response.members[0].role == MemberRole.ADMIN

    def test_membership_response_serialization(self):
        """Test MembershipResponse serialization."""
        user_id = uuid4()
        membership_id = uuid4()

        user_response = UserResponse(id=user_id, username="testuser")

        membership_response = MembershipResponse(
            user_id=user_id,
            role=MemberRole.MEMBER,
            joined_at="2023-01-01T00:00:00Z",
            user=user_response,
        )

        assert membership_response.user_id == user_id
        assert membership_response.role == MemberRole.MEMBER
        assert membership_response.user.username == "testuser"

    def test_invalid_chat_type(self):
        """Test validation with invalid chat type."""
        user1 = uuid4()
        user2 = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(type="invalid_type", participant_ids=[user1, user2])

        assert "Input should be 'dm' or 'group'" in str(exc_info.value)

    def test_invalid_member_role(self):
        """Test validation with invalid member role."""
        user_id = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            AddMemberRequest(user_id=user_id, role="invalid_role")

        assert "Input should be 'member' or 'admin'" in str(exc_info.value)

    def test_invalid_uuid_format(self):
        """Test validation with invalid UUID format."""
        with pytest.raises(ValidationError) as exc_info:
            CreateChatRequest(type=ChatType.DM, participant_ids=["invalid-uuid"])

        assert "Input should be a valid UUID" in str(exc_info.value)
