from starlette.requests import Request

from app.core.http import client_ip


def _request(headers: dict | None = None, client: tuple | None = ("1.2.3.4", 1234)):
    raw = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": raw,
        "client": client,
    }
    return Request(scope)


def test_uses_leftmost_forwarded_for():
    request = _request({"x-forwarded-for": "203.0.113.7, 172.21.0.9"})

    assert client_ip(request) == "203.0.113.7"


def test_normalizes_ipv4_mapped_address():
    request = _request({"x-forwarded-for": "::ffff:203.0.113.7"})

    assert client_ip(request) == "203.0.113.7"


def test_ignores_blank_forwarded_header():
    request = _request({"x-forwarded-for": "   "}, client=("10.0.0.1", 1))

    assert client_ip(request) == "10.0.0.1"


def test_falls_back_to_peer_address():
    request = _request(client=("10.0.0.1", 1))

    assert client_ip(request) == "10.0.0.1"


def test_unknown_when_no_peer():
    request = _request(client=None)

    assert client_ip(request) == "unknown"
