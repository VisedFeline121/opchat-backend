"""Tests for authentication schemas."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    Token,
    TokenRefresh,
    LoginRequest,
)


class TestUserCreate:
    """Test UserCreate schema validation."""

    def test_user_create_valid(self):
        """Test that valid user creation data passes validation."""
        user_data = {"username": "testuser123", "password": "TestPassword123"}
        user = UserCreate(**user_data)
        assert user.username == "testuser123"
        assert user.password == "TestPassword123"

    def test_user_create_weak_password_no_uppercase(self):
        """Test that password without uppercase fails validation."""
        user_data = {"username": "testuser123", "password": "testpassword123"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)
        assert "Password must contain at least one uppercase letter" in str(
            exc_info.value
        )

    def test_user_create_weak_password_no_lowercase(self):
        """Test that password without lowercase fails validation."""
        user_data = {"username": "testuser123", "password": "TESTPASSWORD123"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)
        assert "Password must contain at least one lowercase letter" in str(
            exc_info.value
        )

    def test_user_create_weak_password_no_digit(self):
        """Test that password without digit fails validation."""
        user_data = {"username": "testuser123", "password": "TestPassword"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)
        assert "Password must contain at least one digit" in str(exc_info.value)

    def test_user_create_invalid_username_special_chars(self):
        """Test that username with special characters fails validation."""
        user_data = {"username": "test@user#123", "password": "TestPassword123"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

    def test_user_create_username_too_short(self):
        """Test that username too short fails validation."""
        user_data = {"username": "ab", "password": "TestPassword123"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

    def test_user_create_username_too_long(self):
        """Test that username too long fails validation."""
        user_data = {"username": "a" * 51, "password": "TestPassword123"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

    def test_user_create_password_too_short(self):
        """Test that password too short fails validation."""
        user_data = {"username": "testuser123", "password": "Test1"}
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

    def test_user_create_password_too_long(self):
        """Test that password too long fails validation."""
        user_data = {
            "username": "testuser123",
            "password": "TestPassword123" + "a" * 100,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)


class TestUserUpdate:
    """Test UserUpdate schema validation."""

    def test_user_update_username_only(self):
        """Test updating only username."""
        user_data = {"username": "newusername123"}
        user = UserUpdate(**user_data)
        assert user.username == "newusername123"
        assert user.password is None

    def test_user_update_password_only(self):
        """Test updating only password."""
        user_data = {"password": "NewPassword123"}
        user = UserUpdate(**user_data)
        assert user.password == "NewPassword123"
        assert user.username is None

    def test_user_update_both_fields(self):
        """Test updating both username and password."""
        user_data = {"username": "newusername123", "password": "NewPassword123"}
        user = UserUpdate(**user_data)
        assert user.username == "newusername123"
        assert user.password == "NewPassword123"

    def test_user_update_empty(self):
        """Test updating with no fields."""
        user_data = {}
        user = UserUpdate(**user_data)
        assert user.username is None
        assert user.password is None

    def test_user_update_weak_password(self):
        """Test that weak password in update fails validation."""
        user_data = {"password": "weakpassword"}
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(**user_data)
        assert "Password must contain at least one uppercase letter" in str(
            exc_info.value
        )

    def test_user_update_invalid_username(self):
        """Test that invalid username in update fails validation."""
        user_data = {"username": "invalid@username"}
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(**user_data)


class TestUserResponse:
    """Test UserResponse schema."""

    def test_user_response_from_attributes(self):
        """Test that UserResponse can be created from User attributes."""
        from datetime import datetime
        from uuid import uuid4

        user_data = {
            "id": uuid4(),
            "username": "testuser123",
            "status": "active",
            "last_login_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
        user_response = UserResponse(**user_data)
        assert user_response.username == "testuser123"
        assert user_response.status == "active"


class TestToken:
    """Test Token schema."""

    def test_token_creation(self):
        """Test that token can be created with required fields."""
        token_data = {
            "access_token": "access_token_here",
            "refresh_token": "refresh_token_here",
        }
        token = Token(**token_data)
        assert token.access_token == "access_token_here"
        assert token.refresh_token == "refresh_token_here"
        assert token.token_type == "bearer"

    def test_token_default_type(self):
        """Test that token type defaults to bearer."""
        token_data = {
            "access_token": "access_token_here",
            "refresh_token": "refresh_token_here",
        }
        token = Token(**token_data)
        assert token.token_type == "bearer"


class TestTokenRefresh:
    """Test TokenRefresh schema."""

    def test_token_refresh_creation(self):
        """Test that token refresh can be created."""
        refresh_data = {"refresh_token": "refresh_token_here"}
        token_refresh = TokenRefresh(**refresh_data)
        assert token_refresh.refresh_token == "refresh_token_here"


class TestLoginRequest:
    """Test LoginRequest schema."""

    def test_login_request_creation(self):
        """Test that login request can be created."""
        login_data = {"username": "testuser123", "password": "TestPassword123"}
        login_request = LoginRequest(**login_data)
        assert login_request.username == "testuser123"
        assert login_request.password == "TestPassword123"

    def test_login_request_validation(self):
        """Test that login request validates input."""
        login_data = {"username": "ab", "password": "TestPassword123"}  # Too short
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(**login_data)
