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


async def test_widget_allowed_falls_back_to_tenant(monkeypatch):
    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    seen: dict = {}

    async def capture(identity, limit, **kwargs):
        seen["identity"] = identity
        return True

    monkeypatch.setattr(rate_limit, "check_rate_limit", capture)

    await rate_limit.widget_allowed(None, 7)

    assert seen["identity"] == "tenant:7"
