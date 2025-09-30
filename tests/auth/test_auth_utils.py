"""Tests for authentication utilities."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException, status
from jose import jwt

from app.core.auth_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_active_user,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)
from app.models.user import User, UserStatus


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_verify_password_correct(self):
        """Test that correct password verifies successfully."""
        password = "TestPassword123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password fails verification."""
        password = "TestPassword123"
        wrong_password = "WrongPassword123"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) is False

    def test_get_password_hash(self):
        """Test that password hash is generated and different from plain text."""
        password = "TestPassword123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$argon2")


class TestTokenCreation:
    """Test JWT token creation functions."""

    def test_create_access_token(self):
        """Test that access token is created with correct user_id."""
        user_id = uuid4()
        token = create_access_token(user_id)

        # Decode token to verify contents
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == str(user_id)
        assert "exp" in payload

    def test_create_refresh_token(self):
        """Test that refresh token is created with correct user_id."""
        user_id = uuid4()
        token = create_refresh_token(user_id)

        # Decode token to verify contents
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == str(user_id)
        assert "exp" in payload

    def test_create_token_expiry(self):
        """Test that tokens expire at correct time."""
        user_id = uuid4()
        token = create_access_token(user_id)

        # Decode token to check expiry
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Should expire in approximately 30 minutes
        expected_exp = datetime.now(timezone.utc) + timedelta(minutes=30)
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(
            id=uuid4(),
            username="testuser",
            password_hash="hashed_password",
            status=UserStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def mock_user_repo(self, mock_user):
        """Create a mock user repository."""
        repo = Mock()
        repo.get_user_by_id.return_value = mock_user
        return repo

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_user, mock_user_repo):
        """Test that valid token returns user."""
        token = create_access_token(mock_user.id)

        with patch("app.core.auth_utils.UserRepo", return_value=mock_user_repo):
            # Mock the db session dependency
            with patch("app.core.auth_utils.get_db") as mock_get_db:
                mock_db = mock_get_db.return_value
                result = await get_current_user(token, mock_user_repo, mock_db)
                assert result == mock_user
                mock_user_repo.get_user_by_id.assert_called_once_with(
                    mock_user.id, session=mock_db
                )

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, mock_user_repo):
        """Test that invalid token raises 401."""
        invalid_token = "invalid.token.here"

        with patch("app.core.auth_utils.UserRepo", return_value=mock_user_repo):
            with patch("app.core.auth_utils.get_db") as mock_get_db:
                mock_db = mock_get_db.return_value
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(invalid_token, mock_user_repo, mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, mock_user, mock_user_repo):
        """Test that expired token raises 401."""
        # Create expired token
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {"user_id": str(mock_user.id), "exp": expired_time.timestamp()}
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with patch("app.core.auth_utils.UserRepo", return_value=mock_user_repo):
            with patch("app.core.auth_utils.get_db") as mock_get_db:
                mock_db = mock_get_db.return_value
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(expired_token, mock_user_repo, mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, mock_user_repo):
        """Test that valid token but nonexistent user raises 401."""
        user_id = uuid4()
        token = create_access_token(user_id)
        mock_user_repo.get_user_by_id.return_value = None

        with patch("app.core.auth_utils.UserRepo", return_value=mock_user_repo):
            with patch("app.core.auth_utils.get_db") as mock_get_db:
                mock_db = mock_get_db.return_value
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(token, mock_user_repo, mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""

    @pytest.fixture
    def active_user(self):
        """Create an active user."""
        return User(
            id=uuid4(),
            username="activeuser",
            password_hash="hashed_password",
            status=UserStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def disabled_user(self):
        """Create a disabled user."""
        return User(
            id=uuid4(),
            username="disableduser",
            password_hash="hashed_password",
            status=UserStatus.DISABLED,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self, active_user):
        """Test that active user passes through."""
        result = await get_current_active_user(active_user)
        assert result == active_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled(self, disabled_user):
        """Test that disabled user raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in exc_info.value.detail
