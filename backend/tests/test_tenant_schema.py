import pytest
from pydantic import ValidationError

from app.schemas.tenant import (
    AnswerMode,
    TenantCreate,
    TenantRead,
    slugify_value,
)


def test_slugify_value_normalizes_text():
    assert slugify_value("  My Tenant  ") == "my-tenant"
    assert slugify_value("Hello___World!!") == "hello-world"
    assert slugify_value("already-slug") == "already-slug"


def test_slugify_value_returns_empty_for_non_alphanumeric():
    assert slugify_value("!!!") == ""


def test_tenant_create_normalizes_slug():
    tenant = TenantCreate(name="My Company", slug="  My Company!! ")

    assert tenant.slug == "my-company"


def test_tenant_create_slug_is_optional():
    tenant = TenantCreate(name="My Company")

    assert tenant.slug is None


def test_tenant_create_defaults():
    tenant = TenantCreate(name="Acme", slug="acme")

    assert tenant.name == "Acme"
    assert tenant.default_locale == "it"
    assert tenant.answer_mode is AnswerMode.STRICT


def test_tenant_create_accepts_assistive_mode():
    tenant = TenantCreate(name="Acme", slug="acme", answer_mode="assistive")

    assert tenant.answer_mode is AnswerMode.ASSISTIVE


def test_tenant_create_rejects_invalid_answer_mode():
    with pytest.raises(ValidationError):
        TenantCreate(name="Acme", slug="acme", answer_mode="unknown")


def test_tenant_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        TenantCreate(name="   ", slug="acme")


def test_tenant_create_rejects_invalid_slug():
    with pytest.raises(ValidationError):
        TenantCreate(name="Acme", slug="!!!")


def test_tenant_create_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        TenantCreate(name="Acme", slug="acme", default_locale="fr")


def test_tenant_read_requires_id():
    with pytest.raises(ValidationError):
        TenantRead(name="Acme", slug="acme")

    tenant = TenantRead(id=1, name="Acme", slug="acme")

    assert tenant.id == 1
