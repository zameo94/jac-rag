import pytest
from pydantic import ValidationError

from app.schemas.workspace import (
    AnswerMode,
    WorkspaceCreate,
    WorkspaceRead,
    slugify_value,
)


def test_slugify_value_normalizes_text():
    assert slugify_value("  My Workspace  ") == "my-workspace"
    assert slugify_value("Hello___World!!") == "hello-world"
    assert slugify_value("already-slug") == "already-slug"


def test_slugify_value_returns_empty_for_non_alphanumeric():
    assert slugify_value("!!!") == ""


def test_workspace_create_normalizes_slug():
    workspace = WorkspaceCreate(name="My Company", slug="  My Company!! ")

    assert workspace.slug == "my-company"


def test_workspace_create_slug_is_optional():
    workspace = WorkspaceCreate(name="My Company")

    assert workspace.slug is None


def test_workspace_create_defaults():
    workspace = WorkspaceCreate(name="Acme", slug="acme")

    assert workspace.name == "Acme"
    assert workspace.default_locale == "it"
    assert workspace.answer_mode is AnswerMode.STRICT


def test_workspace_create_accepts_assistive_mode():
    workspace = WorkspaceCreate(name="Acme", slug="acme", answer_mode="assistive")

    assert workspace.answer_mode is AnswerMode.ASSISTIVE


def test_workspace_create_rejects_invalid_answer_mode():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="Acme", slug="acme", answer_mode="unknown")


def test_workspace_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="   ", slug="acme")


def test_workspace_create_rejects_invalid_slug():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="Acme", slug="!!!")


def test_workspace_create_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="Acme", slug="acme", default_locale="fr")


def test_workspace_read_requires_id():
    with pytest.raises(ValidationError):
        WorkspaceRead(name="Acme", slug="acme")

    workspace = WorkspaceRead(id=1, name="Acme", slug="acme")

    assert workspace.id == 1
