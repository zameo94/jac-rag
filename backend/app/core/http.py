from __future__ import annotations

from fastapi import Request

_FORWARDED_FOR = "x-forwarded-for"
_IPV4_MAPPED_PREFIX = "::ffff:"


def _normalize(address: str) -> str:
    if address.startswith(_IPV4_MAPPED_PREFIX):
        return address[len(_IPV4_MAPPED_PREFIX) :]
    return address


def client_ip(request: Request) -> str:
    """Best-effort client address for rate limiting.

    The CMS reaches the API through the Next.js proxy, which sets
    ``X-Forwarded-For``; the leftmost entry is the original client. Direct
    deployments (widget) fall back to the peer address. This assumes the API is
    only reachable through the trusted proxy.
    """
    forwarded = request.headers.get(_FORWARDED_FOR)
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return _normalize(candidate)
    return request.client.host if request.client else "unknown"
