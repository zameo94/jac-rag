import time

from app.core import security
from app.core.config import get_settings
from app.services import rate_limit


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expires: list[tuple[str, int]] = []

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expires.append((key, seconds))


class RaisingRedis:
    async def incr(self, key: str) -> int:
        raise rate_limit.RedisError("connection refused")

    async def expire(self, key: str, seconds: int) -> None:
        raise AssertionError("expire must not run")


async def test_check_rate_limit_allows_until_limit():
    client = FakeRedis()

    assert await rate_limit.check_rate_limit("id", 2, client=client) is True
    assert await rate_limit.check_rate_limit("id", 2, client=client) is True
    assert await rate_limit.check_rate_limit("id", 2, client=client) is False
    assert client.expires


async def test_widget_allowed_disabled_does_not_touch_redis(monkeypatch):
    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "0")
    get_settings.cache_clear()

    async def boom(*args, **kwargs):
        raise AssertionError("check_rate_limit must not be called")

    monkeypatch.setattr(rate_limit, "check_rate_limit", boom)

    assert await rate_limit.widget_allowed("jrk_x", 7) is True


async def test_widget_allowed_hashes_the_embed_key(monkeypatch):
    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    seen: dict = {}

    async def capture(identity, limit, **kwargs):
        seen["identity"] = identity
        seen["limit"] = limit
        return True

    monkeypatch.setattr(rate_limit, "check_rate_limit", capture)

    assert await rate_limit.widget_allowed("jrk_x", 7) is True
    assert seen == {"identity": security.hash_token("jrk_x"), "limit": 5}


async def test_widget_allowed_falls_back_to_workspace(monkeypatch):
    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    seen: dict = {}

    async def capture(identity, limit, **kwargs):
        seen["identity"] = identity
        return True

    monkeypatch.setattr(rate_limit, "check_rate_limit", capture)

    await rate_limit.widget_allowed(None, 7)

    assert seen["identity"] == "workspace:7"


async def test_check_rate_limit_fails_open_on_redis_error():
    assert await rate_limit.check_rate_limit("id", 5, client=RaisingRedis()) is True


async def test_auth_allowed_disabled_does_not_touch_redis(monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "0")
    get_settings.cache_clear()

    def boom(*args, **kwargs):
        raise AssertionError("redis must not be touched")

    monkeypatch.setattr(rate_limit, "get_redis", boom)

    assert await rate_limit.auth_allowed("login", "1.2.3.4") is True


async def test_auth_allowed_counts_by_ip_and_email(monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    client = FakeRedis()

    assert await rate_limit.auth_allowed("login", "1.2.3.4", "User@X.com", client=client) is True
    assert await rate_limit.auth_allowed("login", "1.2.3.4", "user@x.com", client=client) is True
    assert await rate_limit.auth_allowed("login", "1.2.3.4", "user@x.com", client=client) is True
    assert await rate_limit.auth_allowed("login", "1.2.3.4", "user@x.com", client=client) is False

    bucket = time.time() // 60
    assert client.counts[f"ratelimit:auth:login:ip:1.2.3.4:{int(bucket)}"] == 4
    assert client.counts[f"ratelimit:auth:login:email:user@x.com:{int(bucket)}"] == 3


async def test_auth_allowed_ip_exhaustion_rejects_before_email(monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    client = FakeRedis()

    assert await rate_limit.auth_allowed("login", "1.2.3.4", client=client) is True
    assert await rate_limit.auth_allowed("login", "1.2.3.4", client=client) is False


async def test_auth_allowed_without_email_uses_ip_only(monkeypatch):
    monkeypatch.setenv("AUTH_REFRESH_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    client = FakeRedis()

    assert await rate_limit.auth_allowed("refresh", "9.9.9.9", client=client) is True
    assert await rate_limit.auth_allowed("refresh", "9.9.9.9", client=client) is True
    assert await rate_limit.auth_allowed("refresh", "9.9.9.9", client=client) is False

    assert all("email" not in key for key in client.counts)


async def test_auth_allowed_unknown_scope_raises(monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()

    try:
        await rate_limit.auth_allowed("nope", "1.2.3.4", client=FakeRedis())
        raise AssertionError("unknown scope must raise")
    except KeyError:
        pass
