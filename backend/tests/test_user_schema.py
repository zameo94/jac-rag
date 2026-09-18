import pytest
from pydantic import ValidationError

from app.schemas.user import UserBase, UserCreate, UserRead, UserUpdate


def test_user_base_normalizes_email_and_locale():
    user = UserBase(email="  Foo@Bar.IT  ", locale="IT")

    assert user.email == "foo@bar.it"
    assert user.locale == "it"
    assert user.is_active is True


def test_user_base_defaults_locale_to_italian():
    assert UserBase(email="user@example.com").locale == "it"


def test_user_base_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserBase(email="not-an-email")


def test_user_base_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        UserBase(email="user@example.com", locale="fr")


def test_user_create_accepts_valid_payload():
    user = UserCreate(email="User@Example.com")

    assert user.email == "user@example.com"
    assert user.locale == "it"


def test_user_update_allows_partial_payload():
    update = UserUpdate.model_validate({"locale": "en"})

    assert update.locale == "en"
    assert update.email is None
    assert update.is_active is None


def test_user_update_normalizes_provided_email():
    update = UserUpdate.model_validate({"email": "  Mixed@Case.IT "})

    assert update.email == "mixed@case.it"


def test_user_update_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"locale": "de"})


def test_user_read_requires_id():
    with pytest.raises(ValidationError):
        UserRead(email="user@example.com")

    user = UserRead(id=1, email="user@example.com")

    assert user.id == 1
