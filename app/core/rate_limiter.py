"""Rate limiting implementation using Redis with fixed window algorithm."""

import redis
from fastapi import Request

from app.core.config import settings


class RateLimiter:
    """Redis-based rate limiter using fixed window algorithm."""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,
        )

    def _get_ip_key(self, request: Request, endpoint: str) -> str:
        """Get rate limit key based on IP address."""
        client_ip = request.client.host if request.client else "unknown"
        return f"rate_limit:ip:{client_ip}:{endpoint}"

    def _get_user_key(self, user_id: str, endpoint: str) -> str:
        """Get rate limit key based on user ID."""
        return f"rate_limit:user:{user_id}:{endpoint}"

    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check if request is within rate limit using fixed window algorithm."""
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Increment counter (fixed window approach)
            pipe.incr(key)

            # Set expiration only on first request (resets window)
            pipe.expire(key, window)

            # Execute pipeline
            results = pipe.execute()
            current_count = results[0]

            return bool(current_count <= limit)

        except (redis.RedisError, Exception):
            # If Redis is down, allow request (fail open)
            return True

    async def check_ip_rate_limit(
        self, request: Request, endpoint: str, limit: int, window: int = 60
    ) -> bool:
        """Check rate limit based on IP address."""
        key = self._get_ip_key(request, endpoint)
        return await self.check_rate_limit(key, limit, window)

    async def check_user_rate_limit(
        self, user_id: str, endpoint: str, limit: int, window: int = 60
    ) -> bool:
        """Check rate limit based on user ID."""
        key = self._get_user_key(user_id, endpoint)
        return await self.check_rate_limit(key, limit, window)

    async def get_rate_limit_info(self, key: str, limit: int, window: int) -> dict:
        """Get current rate limit information."""
        try:
            current_count = self.redis_client.get(key)
            if current_count is None:
                current_count = 0
            else:
                current_count = int(current_count)

            remaining = max(0, limit - current_count)
            ttl = self.redis_client.ttl(key)

            return {
                "limit": limit,
                "remaining": remaining,
                "reset": ttl if ttl > 0 else window,
            }
        except redis.RedisError:
            return {"limit": limit, "remaining": limit, "reset": window}


# Global rate limiter instance
rate_limiter = RateLimiter()
