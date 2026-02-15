"""
Redis client — singleton connection for pub/sub, caching, and rate limiting.
"""

from __future__ import annotations

import os
from typing import Optional

import redis

from shared.logging.logger import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    Get or create a singleton Redis client.

    Environment variables:
        REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connection
        try:
            _redis_client.ping()
            logger.info("redis_client_initialized", url=url.split("@")[-1])
        except redis.ConnectionError as e:
            logger.error("redis_connection_failed", error=str(e))
            _redis_client = None
            raise

    return _redis_client


def publish_event(channel: str, message: str) -> int:
    """
    Publish a message to a Redis channel.

    Args:
        channel: Redis pub/sub channel name (use CHANNELS constants)
        message: JSON-serialized message string

    Returns:
        Number of subscribers that received the message
    """
    client = get_redis()
    count = client.publish(channel, message)
    logger.debug(
        "redis_publish",
        channel=channel,
        subscribers=count,
        message_size=len(message),
    )
    return count


def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """
    Set a cached value with TTL.

    Args:
        key: Cache key
        value: String value (JSON-serialize before calling)
        ttl_seconds: Time-to-live in seconds (default: 1 hour)
    """
    client = get_redis()
    return client.setex(key, ttl_seconds, value)


def cache_get(key: str) -> Optional[str]:
    """
    Get a cached value.

    Returns:
        Cached string value or None if not found / expired
    """
    client = get_redis()
    return client.get(key)
