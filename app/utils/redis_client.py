"""Async Redis client singleton used for game state, lobby, timers, and votes."""

from redis.asyncio import Redis

from app.config.settings import get_settings

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Return a lazily created, process-wide async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_dsn,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
