import pytest
from pydantic import ValidationError

from app.core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_JWT_SECRET,
    MIN_JWT_SECRET_LENGTH,
    Settings,
    get_settings,
)


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SQL_ECHO", "true")
    monkeypatch.setenv("JWT_SECRET", "a-strong-secret-value-that-is-long-enough")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_url == "sqlite+aiosqlite:///:memory:"
    assert settings.sql_echo is True


def test_settings_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_requires_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_app_metadata_are_code_constants():
    assert APP_NAME == "Jac Rag"
    assert APP_VERSION == "0.1.0"


def test_is_development_true_for_dev_environment():
    assert Settings(_env_file=None, environment="development").is_development is True


def test_is_development_false_for_production_environment():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="a-strong-secret-value-that-is-long-enough",
    )

    assert settings.is_development is False


def test_is_development_normalizes_case_and_spaces():
    assert Settings(_env_file=None, environment="  TEST  ").is_development is True


def test_max_upload_bytes_converts_megabytes():
    assert Settings(_env_file=None, max_upload_mb=3).max_upload_bytes == 3 * 1024 * 1024


def test_cors_origin_list_parses_comma_separated_values():
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_cors_origin_list_ignores_empty_entries():
    settings = Settings(_env_file=None, cors_origins="http://a.test,,  ")

    assert settings.cors_origin_list == ["http://a.test"]


def test_get_settings_is_cached():
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second

    get_settings.cache_clear()


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret=DEFAULT_JWT_SECRET)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", jwt_secret="too-short")


def test_production_accepts_strong_jwt_secret():
    secret = "a-strong-secret-value-that-is-long-enough"

    settings = Settings(_env_file=None, environment="production", jwt_secret=secret)

    assert settings.jwt_secret == secret
    assert len(secret) >= MIN_JWT_SECRET_LENGTH


def test_development_allows_default_jwt_secret():
    settings = Settings(
        _env_file=None, environment="development", jwt_secret=DEFAULT_JWT_SECRET
    )

    assert settings.jwt_secret == DEFAULT_JWT_SECRET
