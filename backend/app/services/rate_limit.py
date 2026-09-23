from __future__ import annotations

import logging
import time

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core import security
from app.core.config import get_settings

logger = logging.getLogger(__name__)

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
    """Fixed-window counter in Redis. Returns False once the limit is exceeded.

    Fail-open: a Redis outage must never lock out legitimate users, so on
    ``RedisError`` the check lets the request through and logs the failure.
    """
    client = client or get_redis()
    bucket = int(time.time() // window_seconds)
    key = f"ratelimit:{identity}:{bucket}"
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
    except RedisError:
        logger.warning("rate limit check failed for %s, failing open", identity)
        return True
    return count <= limit


async def widget_allowed(embed_key: str | None, workspace_id: int) -> bool:
    """Per-embed-key limit (fallback: per-workspace). Disabled when the limit is 0."""
    limit = get_settings().widget_rate_limit_per_minute
    if limit <= 0:
        return True
    identity = security.hash_token(embed_key) if embed_key else f"workspace:{workspace_id}"
    return await check_rate_limit(identity, limit)


async def auth_allowed(scope: str, ip: str, email: str | None = None, *, client=None) -> bool:
    """Per-scope limit for auth endpoints (login/register/refresh/accept).

    Counts by client IP and, when an email is known, by normalized email too,
    so a single user cannot be brute-forced from many addresses. ``0`` disables.
    """
    limit = get_settings().auth_rate_limits[scope]
    if limit <= 0:
        return True
    client = client if client is not None else get_redis()
    ip_ok = await check_rate_limit(f"auth:{scope}:ip:{ip}", limit, client=client)
    if not ip_ok:
        return False
    if email is not None:
        return await check_rate_limit(
            f"auth:{scope}:email:{email.strip().lower()}",
            limit,
            client=client,
        )
    return True
