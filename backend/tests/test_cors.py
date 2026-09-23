from app.core.cors import is_widget_path


def test_is_widget_path_matches_prefix_and_subpaths():
    assert is_widget_path("/api/v1/widget") is True
    assert is_widget_path("/api/v1/widget/session") is True
    assert is_widget_path("/api/v1/widget/chat/stream") is True


def test_is_widget_path_rejects_lookalikes():
    assert is_widget_path("/api/v1/widgets") is False
    assert is_widget_path("/api/v1/workspaces/1/chat") is False


async def test_widget_preflight_allows_any_origin_without_credentials(client):
    response = await client.options(
        "/api/v1/widget/session",
        headers={
            "Origin": "https://shop.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-embed-key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "x-embed-key" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


async def test_widget_preflight_ignores_cms_policy(client):
    response = await client.options(
        "/api/v1/widget/session",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


async def test_widget_simple_request_sets_wildcard_origin(client):
    response = await client.post(
        "/api/v1/widget/session", headers={"Origin": "https://shop.example"}
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "*"


async def test_cms_preflight_allows_configured_origin_with_credentials(client):
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cms_preflight_rejects_unknown_origin(client):
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
