"""Integration tests for chat flows."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.schemas.chat import ChatType, MemberRole


class TestChatFlow:
    """Integration test cases for complete chat flows."""

    def test_complete_dm_creation_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test complete DM creation flow from API to database."""
        # Create users
        alice = user_repo.create_user("alice", "hash123")
        bob = user_repo.create_user("bob", "hash123")

        # Authenticate as alice
        headers = auth_headers_for_user(alice)

        # Create DM via API
        request_data = {
            "type": ChatType.DM,
            "participant_ids": [str(alice.id), str(bob.id)],
        }

        response = client.post("/api/v1/chats/", json=request_data, headers=headers)

        # Should succeed
        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "message" in data
        assert "data" in data
        assert data["data"]["type"] == ChatType.DM
        assert "dm_key" in data["data"]
        assert len(data["data"]["members"]) == 2

        # Verify members
        member_ids = {member["user_id"] for member in data["data"]["members"]}
        assert str(alice.id) in member_ids
        assert str(bob.id) in member_ids

        # Verify all members have MEMBER role
        for member in data["data"]["members"]:
            assert member["role"] == MemberRole.MEMBER

    def test_complete_group_chat_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test complete group chat creation flow from API to database."""
        # Create users
        alice = user_repo.create_user("alice", "hash123")
        bob = user_repo.create_user("bob", "hash123")
        charlie = user_repo.create_user("charlie", "hash123")

        # Authenticate as alice
        headers = auth_headers_for_user(alice)

        # Create group chat via API
        request_data = {
            "type": ChatType.GROUP,
            "participant_ids": [str(alice.id), str(bob.id), str(charlie.id)],
            "topic": "Test Group Chat",
        }

        response = client.post("/api/v1/chats/", json=request_data, headers=headers)

        # Should succeed
        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "message" in data
        assert "data" in data
        assert data["data"]["type"] == ChatType.GROUP
        assert data["data"]["topic"] == "Test Group Chat"
        assert len(data["data"]["members"]) == 3  # Creator + 2 members

        # Verify members
        member_ids = {member["user_id"] for member in data["data"]["members"]}
        assert str(alice.id) in member_ids  # Creator
        assert str(bob.id) in member_ids
        assert str(charlie.id) in member_ids

        # Verify roles
        for member in data["data"]["members"]:
            if member["user_id"] == str(alice.id):
                assert member["role"] == MemberRole.ADMIN  # Creator is admin
            else:
                assert member["role"] == MemberRole.MEMBER

    def test_member_management_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test complete member management flow."""
        # Create users
        alice = user_repo.create_user("alice", "hash123")
        bob = user_repo.create_user("bob", "hash123")
        charlie = user_repo.create_user("charlie", "hash123")
        dave = user_repo.create_user("dave", "hash123")

        # Authenticate as alice
        headers = auth_headers_for_user(alice)

        # Create group chat
        request_data = {
            "type": ChatType.GROUP,
            "participant_ids": [str(alice.id), str(bob.id)],
            "topic": "Test Group",
        }

        response = client.post("/api/v1/chats/", json=request_data, headers=headers)
        assert response.status_code == 201
        chat_data = response.json()
        chat_id = chat_data["data"]["id"]

        # Note: Member addition/removal tests will fail until authentication is implemented
        # For now, we can test the API structure

        # Test adding member (will fail due to authentication)
        add_request = {"user_id": str(charlie.id), "role": MemberRole.MEMBER}

        add_response = client.post(
            f"/api/v1/chats/{chat_id}/members", json=add_request, headers=headers
        )

        # Should succeed since placeholder user is admin
        assert add_response.status_code == 201

        # Test removing member (will fail due to authentication)
        remove_response = client.delete(
            f"/api/v1/chats/{chat_id}/members/{bob.id}", headers=headers
        )

        # Should succeed since placeholder user is admin
        assert remove_response.status_code == 200

    def test_authorization_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test authorization flow for chat access."""
        # Create users
        alice = user_repo.create_user("alice", "hash123")
        bob = user_repo.create_user("bob", "hash123")

        # Authenticate as alice
        headers = auth_headers_for_user(alice)

        # Create DM
        request_data = {
            "type": ChatType.DM,
            "participant_ids": [str(alice.id), str(bob.id)],
        }

        response = client.post("/api/v1/chats/", json=request_data, headers=headers)
        assert response.status_code == 201
        chat_data = response.json()
        chat_id = chat_data["data"]["id"]

        # Test accessing chat details (should succeed since placeholder user is member)
        details_response = client.get(f"/api/v1/chats/{chat_id}", headers=headers)
        assert details_response.status_code == 200  # OK

        # Test accessing chat members (should succeed since placeholder user is member)
        members_response = client.get(
            f"/api/v1/chats/{chat_id}/members", headers=headers
        )
        assert members_response.status_code == 200  # OK

    def test_error_handling_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test error handling flow for various scenarios."""
        # Create a user for authentication
        alice = user_repo.create_user("alice", "hash123")
        headers = auth_headers_for_user(alice)

        # Test invalid chat creation
        invalid_request = {"type": ChatType.DM, "participant_ids": ["invalid-uuid"]}

        response = client.post("/api/v1/chats/", json=invalid_request, headers=headers)
        assert response.status_code == 422  # Validation error

        # Test non-existent chat access
        fake_chat_id = str(uuid4())
        response = client.get(f"/api/v1/chats/{fake_chat_id}", headers=headers)
        assert response.status_code == 404  # Not Found

        # Test invalid UUID format
        response = client.get("/api/v1/chats/invalid-uuid", headers=headers)
        assert response.status_code == 400  # Bad request

    def test_data_consistency_flow(
        self, client: TestClient, user_repo, clean_db, auth_headers_for_user
    ):
        """Test data consistency across operations."""
        # Create users
        alice = user_repo.create_user("alice", "hash123")
        bob = user_repo.create_user("bob", "hash123")

        # Authenticate as alice
        headers = auth_headers_for_user(alice)

        # Create DM
        request_data = {
            "type": ChatType.DM,
            "participant_ids": [str(alice.id), str(bob.id)],
        }

        response = client.post("/api/v1/chats/", json=request_data, headers=headers)
        assert response.status_code == 201
        chat_data = response.json()
        chat_id = chat_data["data"]["id"]

        # Verify DM key consistency
        expected_dm_key = (
            f"{min(str(alice.id), str(bob.id))}::{max(str(alice.id), str(bob.id))}"
        )
        assert chat_data["data"]["dm_key"] == expected_dm_key

        # Verify member count
        assert len(chat_data["data"]["members"]) == 2

        # Verify all members have correct role
        for member in chat_data["data"]["members"]:
            assert member["role"] == MemberRole.MEMBER

        # Verify user IDs are correct
        member_ids = {member["user_id"] for member in chat_data["data"]["members"]}
        assert str(alice.id) in member_ids
        assert str(alice.id) in member_ids
