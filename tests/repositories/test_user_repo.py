"""Tests for UserRepo."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserStatus


class TestUserRepo:
    """Test cases for UserRepo."""

    def test_create_user(self, user_repo, clean_db):
        """Test basic user creation."""
        username = "newuser"
        password_hash = "hashed_password"

        user = user_repo.create_user(username, password_hash)

        assert user.id is not None
        assert user.username == username
        assert user.password_hash == password_hash
        assert user.status == UserStatus.ACTIVE
        assert user.created_at is not None
        assert user.last_login_at is None

    def test_create_user_generates_uuid(self, user_repo, clean_db):
        """Test that user creation generates a UUID."""
        user = user_repo.create_user("testuser", "hash123")

        assert isinstance(user.id, type(uuid4()))
        assert str(user.id) != ""

    def test_create_duplicate_username(self, user_repo, sample_user):
        """Test that duplicate username raises IntegrityError."""
        with pytest.raises(IntegrityError):
            user_repo.create_user(sample_user.username, "different_hash")

    def test_get_by_id_existing(self, user_repo, sample_user):
        """Test retrieving existing user by ID."""
        user = user_repo.get_user_by_id(sample_user.id)

        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username

    def test_get_by_id_not_found(self, user_repo, clean_db):
        """Test that non-existent user ID returns None."""
        non_existent_id = uuid4()
        user = user_repo.get_user_by_id(non_existent_id)

        assert user is None

    def test_get_by_username_existing(self, user_repo, sample_user):
        """Test retrieving existing user by username."""
        user = user_repo.get_by_username(sample_user.username)

        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username

    def test_get_by_username_not_found(self, user_repo, clean_db):
        """Test that non-existent username returns None."""
        user = user_repo.get_by_username("nonexistent")

        assert user is None

    def test_get_all_users(self, user_repo, sample_users):
        """Test retrieving all users."""
        users = user_repo.get_all_users()

        assert len(users) == len(sample_users)
        usernames = {user.username for user in users}
        expected_usernames = {user.username for user in sample_users}
        assert usernames == expected_usernames

    def test_get_all_users_empty(self, user_repo, clean_db):
        """Test get_all_users returns empty list when no users."""
        users = user_repo.get_all_users()

        assert users == []

    def test_update_last_login_at(self, user_repo, sample_user):
        """Test updating last login timestamp."""
        login_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        updated_user = user_repo.update_last_login_at(sample_user.id, login_time)

        assert updated_user is not None
        assert updated_user.id == sample_user.id
        assert updated_user.last_login_at == login_time

    def test_update_last_login_at_not_found(self, user_repo, clean_db):
        """Test updating last login for non-existent user returns None."""
        non_existent_id = uuid4()
        login_time = datetime.now(timezone.utc)

        result = user_repo.update_last_login_at(non_existent_id, login_time)

        assert result is None

    def test_delete_user(self, user_repo, sample_user):
        """Test user deletion."""
        user_id = sample_user.id

        user_repo.delete_user(user_id)

        # Verify user is deleted
        deleted_user = user_repo.get_user_by_id(user_id)
        assert deleted_user is None

    def test_delete_user_not_found(self, user_repo, clean_db):
        """Test deleting non-existent user doesn't raise error."""
        non_existent_id = uuid4()

        # Should not raise exception
        user_repo.delete_user(non_existent_id)

    def test_create_user_auto_commit_mode(self, user_repo, clean_db):
        """Test that auto-commit mode works (no external session)."""
        user = user_repo.create_user("autocommit_user", "hash123")

        # Verify user is persisted (can be retrieved in new session)
        retrieved = user_repo.get_user_by_id(user.id)
        assert retrieved is not None
        assert retrieved.username == "autocommit_user"

    def test_create_user_coordinated_mode(self, user_repo, test_session, clean_db):
        """Test that coordinated mode works (with external session)."""
        username = "coordinated_user"

        # Use external session
        user = user_repo.create_user(username, "hash123", session=test_session)

        # User should exist in the session but not committed yet
        assert user.username == username

        # Commit the external session
        test_session.commit()

        # Now should be retrievable
        retrieved = user_repo.get_by_username(username)
        assert retrieved is not None
        assert retrieved.username == username
