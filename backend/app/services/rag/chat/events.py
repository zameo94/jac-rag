from __future__ import annotations

import json


def sse_event(name: str, data: dict) -> str:
    """Encode one Server-Sent Event (``event:`` + ``data:`` + blank line)."""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
