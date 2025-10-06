"""Tests for rate limiting functionality."""

import pytest
import redis
from unittest.mock import Mock, patch
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limiting.rate_limiter import RateLimiter, rate_limiter
from app.core.config.config import settings


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_rate_limiter_initialization(self):
        """Test that rate limiter initializes correctly."""
        assert rate_limiter is not None
        assert rate_limiter.redis_client is not None

    @pytest.mark.asyncio
    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.redis_client")
    async def test_check_rate_limit_allowed(self, mock_redis):
        """Test rate limit check when request is allowed."""
        # Mock Redis pipeline
        mock_pipe = Mock()
        mock_pipe.incr.return_value = mock_pipe
        mock_pipe.expire.return_value = mock_pipe
        mock_pipe.execute.return_value = [5]  # Current count is 5
        mock_redis.pipeline.return_value = mock_pipe

        # Test with limit of 10
        result = await rate_limiter.check_rate_limit("test_key", 10, 60)
        assert result is True

    @pytest.mark.asyncio
    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.redis_client")
    async def test_check_rate_limit_exceeded(self, mock_redis):
        """Test rate limit check when request is exceeded."""
        # Mock Redis pipeline
        mock_pipe = Mock()
        mock_pipe.incr.return_value = mock_pipe
        mock_pipe.expire.return_value = mock_pipe
        mock_pipe.execute.return_value = [15]  # Current count is 15
        mock_redis.pipeline.return_value = mock_pipe

        # Test with limit of 10
        result = await rate_limiter.check_rate_limit("test_key", 10, 60)
        assert result is False

    @pytest.mark.asyncio
    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.redis_client")
    async def test_check_rate_limit_redis_error_fail_open(self, mock_redis):
        """Test that rate limiter fails open when Redis is down (allows requests)."""
        # Mock Redis error during pipeline execution
        mock_pipe = Mock()
        mock_pipe.incr.return_value = mock_pipe
        mock_pipe.expire.return_value = mock_pipe
        mock_pipe.execute.side_effect = Exception("Redis connection failed")
        mock_redis.pipeline.return_value = mock_pipe

        # CRITICAL: When Redis fails, we should ALLOW the request (fail-open)
        # This prevents Redis outages from breaking the entire API
        result = await rate_limiter.check_rate_limit("test_key", 10, 60)
        assert result is True, "Rate limiter should fail-open when Redis is down"

        # Verify that the Redis operations were attempted before failing
        mock_redis.pipeline.assert_called_once()
        mock_pipe.incr.assert_called_once_with("test_key")
        mock_pipe.expire.assert_called_once_with("test_key", 60)
        mock_pipe.execute.assert_called_once()

    def test_get_ip_key(self):
        """Test IP key generation."""
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"

        key = rate_limiter._get_ip_key(mock_request, "login")
        assert key == "rate_limit:ip:192.168.1.1:login"

    def test_get_user_key(self):
        """Test user key generation."""
        key = rate_limiter._get_user_key("user123", "profile")
        assert key == "rate_limit:user:user123:profile"


class TestRateLimiterRedisIntegration:
    """Test rate limiter with real Redis connection using fixed window algorithm."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=1,  # Use different DB for tests
            decode_responses=True,
        )
        # Test connection
        client.ping()
        # Clear test database
        client.flushdb()
        yield client
        # Clean up after test
        client.flushdb()
        client.close()

    @pytest.fixture
    def test_rate_limiter(self, redis_client):
        """Create rate limiter with test Redis client."""

        limiter = RateLimiter()
        limiter.redis_client = redis_client
        return limiter

    @pytest.mark.asyncio
    async def test_real_redis_rate_limit_allowed(self, test_rate_limiter):
        """Test rate limiting with real Redis - requests allowed."""
        # First 5 requests should be allowed
        for i in range(5):
            result = await test_rate_limiter.check_rate_limit("test_key", 10, 60)
            assert result is True, f"Request {i+1} should be allowed"

    @pytest.mark.asyncio
    async def test_real_redis_rate_limit_exceeded(self, test_rate_limiter):
        """Test rate limiting with real Redis - requests exceeded."""
        # First 10 requests should be allowed
        for i in range(10):
            result = await test_rate_limiter.check_rate_limit("test_key", 10, 60)
            assert result is True, f"Request {i+1} should be allowed"

        # 11th request should be blocked
        result = await test_rate_limiter.check_rate_limit("test_key", 10, 60)
        assert result is False, "11th request should be blocked"

    @pytest.mark.asyncio
    async def test_real_redis_different_keys(self, test_rate_limiter):
        """Test that different keys have separate rate limits."""
        # Use up limit for key1
        for i in range(10):
            result = await test_rate_limiter.check_rate_limit("key1", 10, 60)
            assert result is True

        # key1 should now be blocked
        result = await test_rate_limiter.check_rate_limit("key1", 10, 60)
        assert result is False

        # key2 should still work
        result = await test_rate_limiter.check_rate_limit("key2", 10, 60)
        assert result is True

    @pytest.mark.asyncio
    async def test_real_redis_expiration(self, test_rate_limiter):
        """Test that rate limits expire after TTL."""
        # Use up the limit
        for i in range(10):
            result = await test_rate_limiter.check_rate_limit(
                "test_key", 10, 1
            )  # 1 second TTL
            assert result is True

        # Should be blocked
        result = await test_rate_limiter.check_rate_limit("test_key", 10, 1)
        assert result is False

        # Wait for expiration
        import time

        time.sleep(1.1)

        # Should work again
        result = await test_rate_limiter.check_rate_limit("test_key", 10, 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_real_redis_ip_rate_limiting(self, test_rate_limiter):
        """Test IP-based rate limiting with real Redis."""
        # Mock request objects
        request1 = Mock()
        request1.client.host = "192.168.1.1"

        request2 = Mock()
        request2.client.host = "192.168.1.2"

        # Use up limit for IP 1
        for i in range(10):
            result = await test_rate_limiter.check_ip_rate_limit(
                request1, "login", 10, 60
            )
            assert result is True

        # IP 1 should be blocked
        result = await test_rate_limiter.check_ip_rate_limit(request1, "login", 10, 60)
        assert result is False

        # IP 2 should still work
        result = await test_rate_limiter.check_ip_rate_limit(request2, "login", 10, 60)
        assert result is True


class TestRateLimitingIntegration:
    """Test rate limiting integration with auth endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.check_ip_rate_limit")
    def test_signup_rate_limiting(self, mock_rate_limit, client):
        """Test that signup endpoint respects rate limiting."""
        # Mock rate limit check to return False (rate limited)
        mock_rate_limit.return_value = False

        response = client.post(
            "/api/v1/auth/signup",
            json={"username": "testuser", "password": "TestPassword123"},
        )

        assert response.status_code == 429
        assert "Too many signup attempts" in response.json()["detail"]

    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.check_ip_rate_limit")
    def test_login_rate_limiting(self, mock_rate_limit, client):
        """Test that login endpoint respects rate limiting."""
        # Mock rate limit check to return False (rate limited)
        mock_rate_limit.return_value = False

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "TestPassword123"},
        )

        assert response.status_code == 429
        assert "Too many login attempts" in response.json()["detail"]

    @patch("app.core.rate_limiting.rate_limiter.rate_limiter.check_ip_rate_limit")
    def test_refresh_rate_limiting(self, mock_rate_limit, client):
        """Test that refresh endpoint respects rate limiting."""
        # Mock rate limit check to return False (rate limited)
        mock_rate_limit.return_value = False

        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "fake_token"}
        )

        assert response.status_code == 429
        assert "Too many refresh attempts" in response.json()["detail"]


class TestRealRedisAuthIntegration:
    """Test auth endpoints with real Redis rate limiting."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=2,  # Use different DB for auth tests
            decode_responses=True,
        )
        # Test connection
        client.ping()
        # Clear test database
        client.flushdb()
        yield client
        # Clean up after test
        client.flushdb()
        client.close()

    @pytest.fixture
    def client_with_real_redis(self, redis_client):
        """Create test client with real Redis rate limiting."""
        # Patch the rate limiter to use our test Redis
        with patch(
            "app.core.rate_limiting.rate_limiter.rate_limiter.redis_client",
            redis_client,
        ):
            yield TestClient(app)

    def test_real_redis_signup_rate_limiting(self, client_with_real_redis):
        """Test signup rate limiting with real Redis."""
        # First 5 signups should work
        for i in range(5):
            response = client_with_real_redis.post(
                "/api/v1/auth/signup",
                json={"username": f"testuser{i}", "password": "TestPassword123"},
            )
            assert response.status_code == 201, f"Signup {i+1} should succeed"

        # 6th signup should be rate limited
        response = client_with_real_redis.post(
            "/api/v1/auth/signup",
            json={"username": "testuser6", "password": "TestPassword123"},
        )
        assert response.status_code == 429
        assert "Too many signup attempts" in response.json()["detail"]

    def test_real_redis_login_rate_limiting(self, client_with_real_redis):
        """Test login rate limiting with real Redis."""
        # First create a user
        client_with_real_redis.post(
            "/api/v1/auth/signup",
            json={"username": "testuser", "password": "TestPassword123"},
        )

        # First 10 login attempts should work
        for i in range(10):
            response = client_with_real_redis.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "TestPassword123"},
            )
            assert response.status_code == 200, f"Login {i+1} should succeed"

        # 11th login attempt should be rate limited
        response = client_with_real_redis.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "TestPassword123"},
        )
        assert response.status_code == 429
        assert "Too many login attempts" in response.json()["detail"]
