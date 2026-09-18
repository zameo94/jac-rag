from app.core.errors import api_error


def test_api_error_builds_payload_without_details():
    exception = api_error(404, "NOT_FOUND", "Missing resource")

    assert exception.status_code == 404
    assert exception.detail == {"code": "NOT_FOUND", "message": "Missing resource"}


def test_api_error_includes_details_when_provided():
    exception = api_error(409, "CONFLICT", "Clash", details={"field": "email"})

    assert exception.detail == {
        "code": "CONFLICT",
        "message": "Clash",
        "details": {"field": "email"},
    }
