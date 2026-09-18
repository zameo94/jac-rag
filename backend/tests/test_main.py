from app.main import app


async def test_health_returns_ok(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_metadata():
    assert app.title == "Jac Rag"
    assert app.version == "0.1.0"


async def test_unknown_route_returns_structured_error(client):
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == "HTTP_ERROR"
