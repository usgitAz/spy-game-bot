"""Async Redis client singleton used for game state, lobby, timers, and votes."""

from __future__ import annotations

from redis.asyncio import Redis

from app.config.settings import get_settings

_redis_client: Redis | None = None


def build_redis(url: str, *, decode_responses: bool = True) -> Redis:
    """Create a Redis client compatible with older Redis servers."""
    kwargs: dict = {"decode_responses": decode_responses}
    try:
        from redis.maint_notifications import MaintNotificationsConfig

        kwargs["maint_notifications_config"] = MaintNotificationsConfig(enabled=False)
    except ImportError:
        # Older redis-py without this module — nothing to disable.
        pass

    return Redis.from_url(url, **kwargs)


def get_redis() -> Redis:
    """Return a lazily created, process-wide async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = build_redis(settings.redis_dsn, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
