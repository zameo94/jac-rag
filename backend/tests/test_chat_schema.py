import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest


def test_chat_request_locale_is_optional():
    request = ChatRequest(message="ciao")

    assert request.locale is None
    assert request.conversation_id is None


def test_chat_request_normalizes_locale():
    request = ChatRequest(message="hello", locale="EN")

    assert request.locale == "en"


def test_chat_request_accepts_explicit_null_locale():
    request = ChatRequest.model_validate({"message": "ciao", "locale": None})

    assert request.locale is None


def test_chat_request_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        ChatRequest(message="ciao", locale="fr")


def test_chat_request_rejects_blank_locale():
    with pytest.raises(ValidationError):
        ChatRequest(message="ciao", locale="   ")
