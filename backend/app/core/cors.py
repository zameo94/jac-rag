from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware

WIDGET_PATH_PREFIX = "/api/v1/widget"
WIDGET_ALLOW_HEADERS = ["Content-Type", "X-Embed-Key", "X-Visitor-Token"]
WIDGET_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]


def is_widget_path(path: str) -> bool:
    return path == WIDGET_PATH_PREFIX or path.startswith(f"{WIDGET_PATH_PREFIX}/")


class CorsDispatcher:
    """Apply two CORS policies to one ASGI app.

    The widget API authenticates with a bearer embed key, never cookies, so it
    allows any origin without credentials. The CMS keeps the credentialed
    policy restricted to the configured origins. Only one policy runs per
    request, so no duplicate/conflicting CORS headers are emitted.
    """

    def __init__(
        self,
        app,
        *,
        cms_origins: list[str],
        cms_allow_headers: list[str],
    ) -> None:
        self.cms = CORSMiddleware(
            app,
            allow_origins=cms_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=cms_allow_headers,
        )
        self.widget = CORSMiddleware(
            app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=WIDGET_ALLOW_METHODS,
            allow_headers=WIDGET_ALLOW_HEADERS,
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and is_widget_path(scope.get("path", "")):
            await self.widget(scope, receive, send)
        else:
            await self.cms(scope, receive, send)
