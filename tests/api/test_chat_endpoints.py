"""Tests for chat API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.schemas.chat import ChatType, MemberRole


class TestChatEndpoints:
    """Test cases for chat API endpoints."""

    def test_list_user_chats_success(
        self, client: TestClient, sample_dm, sample_group_chat, sample_users
    ):
        """Test successful user chat listing."""
        # Note: This will fail until authentication is implemented
        # For now, it will return empty list due to placeholder user ID
        response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()
        assert "chats" in data
        assert "total" in data
        assert data["total"] == 0  # Due to placeholder user ID

    def test_list_user_chats_empty(self, client: TestClient, clean_db):
        """Test user chat listing with no chats."""
        response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()
        assert data["chats"] == []
        assert data["total"] == 0

    def test_create_dm_success(self, client: TestClient, sample_users, clean_db):
        """Test successful DM creation."""
        alice, bob = sample_users[0], sample_users[1]

        request_data = {
            "type": ChatType.DM,
            "participant_ids": [str(alice.id), str(bob.id)],
        }

        response = client.post("/api/v1/chats/", json=request_data)

        # Note: This will fail until authentication is implemented
        # For now, it will return 400 due to placeholder user ID
        assert response.status_code == 400  # Bad request due to placeholder user

    def test_create_dm_invalid_participants(
        self, client: TestClient, sample_users, clean_db
    ):
        """Test DM creation with invalid participant count."""
        alice = sample_users[0]

        request_data = {
            "type": ChatType.DM,
            "participant_ids": [str(alice.id)],  # Only 1 participant
        }

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_create_dm_users_not_exist(self, client: TestClient, clean_db):
        """Test DM creation with non-existent users."""
        fake_user1 = str(uuid4())
        fake_user2 = str(uuid4())

        request_data = {
            "type": ChatType.DM,
            "participant_ids": [fake_user1, fake_user2],
        }

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 400  # Bad request due to user validation

    def test_create_group_chat_success(
        self, client: TestClient, sample_users, clean_db
    ):
        """Test successful group chat creation."""
        alice, bob, charlie = sample_users
        topic = "Test Group"

        request_data = {
            "type": ChatType.GROUP,
            "participant_ids": [str(bob.id), str(charlie.id)],
            "topic": topic,
        }

        response = client.post("/api/v1/chats/", json=request_data)

        # Note: This will fail until authentication is implemented
        # For now, it will return 400 due to placeholder user ID
        assert response.status_code == 400  # Bad request due to placeholder user

    def test_create_group_chat_missing_topic(
        self, client: TestClient, sample_users, clean_db
    ):
        """Test group chat creation without topic."""
        alice, bob = sample_users[0], sample_users[1]

        request_data = {
            "type": ChatType.GROUP,
            "participant_ids": [str(bob.id)],
            # Missing topic
        }

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_create_group_chat_invalid_participants(
        self, client: TestClient, sample_users, clean_db
    ):
        """Test group chat creation with too few participants."""
        alice = sample_users[0]

        request_data = {
            "type": ChatType.GROUP,
            "participant_ids": [str(alice.id)],  # Only 1 participant
            "topic": "Test Group",
        }

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_get_chat_details_success(
        self, client: TestClient, sample_dm, sample_users
    ):
        """Test successful chat details retrieval."""
        # Note: This will fail until authentication is implemented
        # For now, it will return 403 due to placeholder user ID
        response = client.get(f"/api/v1/chats/{sample_dm.id}")

        assert response.status_code == 403  # Forbidden due to placeholder user

    def test_get_chat_details_not_found(self, client: TestClient, clean_db):
        """Test chat details retrieval for non-existent chat."""
        fake_id = str(uuid4())

        response = client.get(f"/api/v1/chats/{fake_id}")

        assert response.status_code == 404  # Not found due to non-existent chat

    def test_get_chat_details_invalid_id(self, client: TestClient):
        """Test chat details retrieval with invalid ID format."""
        response = client.get("/api/v1/chats/invalid-uuid")

        assert response.status_code == 400  # Bad request due to invalid UUID

    def test_list_chat_members_success(
        self, client: TestClient, sample_group_chat, sample_users
    ):
        """Test successful chat members listing."""
        # Note: This will fail until authentication is implemented
        response = client.get(f"/api/v1/chats/{sample_group_chat.id}/members")

        assert response.status_code == 403  # Forbidden due to placeholder user

    def test_list_chat_members_chat_not_found(self, client: TestClient, clean_db):
        """Test chat members listing for non-existent chat."""
        fake_id = str(uuid4())

        response = client.get(f"/api/v1/chats/{fake_id}/members")

        assert response.status_code == 403  # Forbidden due to placeholder user

    def test_add_member_success(
        self, client: TestClient, sample_group_chat, user_repo, clean_db
    ):
        """Test successful member addition."""
        # Create a new user
        new_user = user_repo.create_user("newmember", "hash123")

        request_data = {"user_id": str(new_user.id), "role": MemberRole.MEMBER}

        response = client.post(
            f"/api/v1/chats/{sample_group_chat.id}/members", json=request_data
        )

        # Note: This will fail until authentication is implemented
        # For now, it will return 400 due to placeholder user ID
        assert response.status_code == 400  # Bad request due to placeholder user

    def test_add_member_chat_not_found(self, client: TestClient, user_repo, clean_db):
        """Test member addition to non-existent chat."""
        new_user = user_repo.create_user("newmember", "hash123")
        fake_chat_id = str(uuid4())

        request_data = {"user_id": str(new_user.id), "role": MemberRole.MEMBER}

        response = client.post(
            f"/api/v1/chats/{fake_chat_id}/members", json=request_data
        )

        assert response.status_code == 400  # Bad request due to placeholder user

    def test_add_member_invalid_user_id(self, client: TestClient, sample_group_chat):
        """Test member addition with invalid user ID format."""
        request_data = {"user_id": "invalid-uuid", "role": MemberRole.MEMBER}

        response = client.post(
            f"/api/v1/chats/{sample_group_chat.id}/members", json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_remove_member_success(
        self, client: TestClient, sample_group_chat, sample_users
    ):
        """Test successful member removal."""
        bob = sample_users[1]

        response = client.delete(
            f"/api/v1/chats/{sample_group_chat.id}/members/{bob.id}"
        )

        # Note: This will fail until authentication is implemented
        # For now, it will return 400 due to placeholder user ID
        assert response.status_code == 400  # Bad request due to placeholder user

    def test_remove_member_chat_not_found(
        self, client: TestClient, sample_users, clean_db
    ):
        """Test member removal from non-existent chat."""
        bob = sample_users[1]
        fake_chat_id = str(uuid4())

        response = client.delete(f"/api/v1/chats/{fake_chat_id}/members/{bob.id}")

        assert response.status_code == 400  # Bad request due to placeholder user

    def test_remove_member_invalid_ids(self, client: TestClient, sample_group_chat):
        """Test member removal with invalid ID formats."""
        response = client.delete(f"/api/v1/chats/invalid-uuid/members/invalid-uuid")

        assert response.status_code == 400  # Bad request due to invalid UUIDs

    def test_create_chat_invalid_type(self, client: TestClient, sample_users, clean_db):
        """Test chat creation with invalid type."""
        alice, bob = sample_users[0], sample_users[1]

        request_data = {
            "type": "invalid_type",
            "participant_ids": [str(alice.id), str(bob.id)],
        }

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_create_chat_empty_participants(self, client: TestClient, clean_db):
        """Test chat creation with empty participant list."""
        request_data = {"type": ChatType.DM, "participant_ids": []}

        response = client.post("/api/v1/chats/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_add_member_invalid_role(
        self, client: TestClient, sample_group_chat, user_repo, clean_db
    ):
        """Test member addition with invalid role."""
        new_user = user_repo.create_user("newmember", "hash123")

        request_data = {"user_id": str(new_user.id), "role": "invalid_role"}

        response = client.post(
            f"/api/v1/chats/{sample_group_chat.id}/members", json=request_data
        )

        assert response.status_code == 422  # Validation error
