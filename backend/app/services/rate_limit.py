from __future__ import annotations

import time

import redis.asyncio as redis

from app.core import security
from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url)
    return _client


async def check_rate_limit(
    identity: str,
    limit: int,
    *,
    window_seconds: int = 60,
    client=None,
) -> bool:
    """Fixed-window counter in Redis. Returns False once the limit is exceeded."""
    client = client or get_redis()
    bucket = int(time.time() // window_seconds)
    key = f"ratelimit:{identity}:{bucket}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)
    return count <= limit


async def widget_allowed(embed_key: str | None, tenant_id: int) -> bool:
    """Per-embed-key limit (fallback: per-tenant). Disabled when the limit is 0."""
    limit = get_settings().widget_rate_limit_per_minute
    if limit <= 0:
        return True
    identity = security.hash_token(embed_key) if embed_key else f"tenant:{tenant_id}"
    return await check_rate_limit(identity, limit)
