"""Integration tests for authentication flows."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepo
from app.core.auth_utils import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
)


# Use the client fixture from the main conftest.py


@pytest.fixture
def test_user_data():
    """Test user data for signup."""
    return {"username": "testuser123", "password": "TestPassword123"}


@pytest.fixture
def test_user(test_session_factory):
    """Create a test user in the database."""
    user_repo = UserRepo(test_session_factory)
    user = user_repo.create_user(
        username="testuser123", password_hash=get_password_hash("TestPassword123")
    )
    return user


class TestSignupFlow:
    """Test user signup flow."""

    def test_signup_success(self, client, test_user_data):
        """Test successful user signup."""
        response = client.post("/api/v1/auth/signup", json=test_user_data)
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_signup_duplicate_username(self, client, test_user_data, test_user):
        """Test signup with duplicate username fails."""
        response = client.post("/api/v1/auth/signup", json=test_user_data)
        assert response.status_code == 409
        assert "username already exists" in response.json()["detail"].lower()

    def test_signup_weak_password(self, client):
        """Test signup with weak password fails."""
        weak_user_data = {"username": "newuser123", "password": "weak"}
        response = client.post("/api/v1/auth/signup", json=weak_user_data)
        assert response.status_code == 422
        assert "password" in str(response.json())


class TestLoginFlow:
    """Test user login flow."""

    def test_login_success(self, client, test_user):
        """Test successful login returns tokens."""
        login_data = {"username": "testuser123", "password": "TestPassword123"}
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials fails."""
        login_data = {"username": "testuser123", "password": "WrongPassword123"}
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user fails."""
        login_data = {"username": "nonexistentuser", "password": "TestPassword123"}
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()


class TestProtectedEndpoints:
    """Test protected endpoint access."""

    def test_protected_endpoint_with_valid_token(self, client, test_user):
        """Test that valid token allows access to protected endpoint."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["username"] == test_user.username

    def test_protected_endpoint_without_token(self, client):
        """Test that missing token denies access to protected endpoint."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    def test_protected_endpoint_with_invalid_token(self, client):
        """Test that invalid token denies access to protected endpoint."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert "could not validate credentials" in response.json()["detail"].lower()

    def test_protected_endpoint_disabled_user(self, client, test_session_factory):
        """Test that disabled user cannot access protected endpoints."""
        user_repo = UserRepo(test_session_factory)
        disabled_user = user_repo.create_user(
            username="disableduser", password_hash=get_password_hash("TestPassword123")
        )

        # Actually disable the user
        disabled_user.status = UserStatus.DISABLED
        session = test_session_factory()
        session.add(disabled_user)
        session.commit()
        session.close()

        token = create_access_token(disabled_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 400
        assert "inactive user" in response.json()["detail"].lower()


class TestTokenRefresh:
    """Test token refresh functionality."""

    def test_refresh_token_success(self, client, test_user):
        """Test successful token refresh."""
        # First login to get refresh token
        login_data = {"username": "testuser123", "password": "TestPassword123"}
        login_response = client.post("/api/v1/auth/login", json=login_data)
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new tokens
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token fails."""
        refresh_data = {"refresh_token": "invalid_token"}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401
        assert "invalid refresh token" in response.json()["detail"].lower()

    def test_refresh_token_expired(self, client, test_user):
        """Test refresh with expired token fails."""
        # Create an expired refresh token
        from datetime import datetime, timedelta
        from jose import jwt
        from app.core.auth_utils import JWT_SECRET_KEY, JWT_ALGORITHM

        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {"user_id": str(test_user.id), "exp": expired_time.timestamp()}
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        refresh_data = {"refresh_token": expired_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401
        assert "invalid refresh token" in response.json()["detail"].lower()

    def test_refresh_token_disabled_user(self, client, test_session_factory):
        """Test refresh token for disabled user fails."""
        user_repo = UserRepo(test_session_factory)
        disabled_user = user_repo.create_user(
            username="disableduser", password_hash=get_password_hash("TestPassword123")
        )

        # Actually disable the user
        disabled_user.status = UserStatus.DISABLED
        session = test_session_factory()
        session.add(disabled_user)
        session.commit()
        session.close()

        # Create refresh token for disabled user
        refresh_token = create_refresh_token(disabled_user.id)
        refresh_data = {"refresh_token": refresh_token}

        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 401
        assert "user not found or inactive" in response.json()["detail"].lower()


class TestUserProfile:
    """Test user profile management."""

    def test_get_profile_success(self, client, test_user):
        """Test getting user profile with valid token."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["username"] == test_user.username
        assert data["status"] == test_user.status.value

    def test_update_profile_username(self, client, test_user):
        """Test updating username successfully."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {"username": "newusername123"}
        response = client.put("/api/v1/auth/me", json=update_data, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newusername123"

    def test_update_profile_password(self, client, test_user):
        """Test updating password successfully."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {"password": "NewPassword123"}
        response = client.put("/api/v1/auth/me", json=update_data, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username  # Username unchanged

    def test_update_profile_duplicate_username(
        self, client, test_user, test_session_factory
    ):
        """Test updating to existing username fails."""
        # Create another user
        user_repo = UserRepo(test_session_factory)
        other_user = user_repo.create_user(
            username="otheruser", password_hash=get_password_hash("TestPassword123")
        )

        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # Try to update to existing username
        update_data = {"username": "otheruser"}
        response = client.put("/api/v1/auth/me", json=update_data, headers=headers)

        assert response.status_code == 409
        assert "username already exists" in response.json()["detail"].lower()

    def test_delete_account_success(self, client, test_user):
        """Test deleting account successfully."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.delete("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert "successfully deleted" in response.json()["message"].lower()

        # Verify user can no longer access profile
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


class TestLogout:
    """Test logout functionality."""

    def test_logout_success(self, client, test_user):
        """Test successful logout."""
        token = create_access_token(test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 200
        assert "successfully logged out" in response.json()["message"].lower()

    def test_logout_requires_auth(self, client):
        """Test logout without token fails."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 401


class TestUserRepositoryIntegration:
    """Test user repository integration with auth."""

    def test_user_creation_and_retrieval(self, test_session_factory):
        """Test that user can be created and retrieved."""
        user_repo = UserRepo(test_session_factory)

        # Create user
        user = user_repo.create_user(
            username="integrationtest",
            password_hash=get_password_hash("TestPassword123"),
        )

        # Retrieve user
        retrieved_user = user_repo.get_user_by_id(user.id)
        assert retrieved_user is not None
        assert retrieved_user.username == "integrationtest"
        assert retrieved_user.status == UserStatus.ACTIVE

    def test_user_authentication_flow(self, test_session_factory):
        """Test complete authentication flow with repository."""
        user_repo = UserRepo(test_session_factory)

        # Create user
        password = "TestPassword123"
        user = user_repo.create_user(
            username="authtest", password_hash=get_password_hash(password)
        )

        # Verify password
        from app.core.auth_utils import verify_password

        assert verify_password(password, user.password_hash)

        # Create token
        token = create_access_token(user.id)
        assert token is not None

        # Verify token contains correct user_id
        from jose import jwt
        from app.core.auth_utils import JWT_SECRET_KEY, JWT_ALGORITHM

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == str(user.id)
