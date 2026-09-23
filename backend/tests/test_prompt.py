from app.schemas.workspace import AnswerMode
from app.services.rag.chat.prompt import build_messages, refusal_message
from app.services.rag.vector_store import RetrievedChunk

CHUNK = RetrievedChunk(
    document_id=1,
    chunk_index=0,
    text="Il colore preferito e il blu.",
    score=0.9,
    filename="doc.md",
)


def system_content(locale, mode: AnswerMode = AnswerMode.STRICT) -> str:
    messages = build_messages("domanda", [CHUNK], answer_mode=mode, locale=locale)
    return messages[0].content


def test_strict_prompt_answers_in_english_for_english_locale():
    content = system_content("en")

    assert "Always answer in English." in content
    assert "language of the question" not in content


def test_strict_prompt_answers_in_italian_for_italian_locale():
    content = system_content("it")

    assert "Rispondi sempre in italiano." in content
    assert "lingua della domanda" not in content


def test_assistive_prompt_follows_the_locale():
    assert "Always answer in English." in system_content("en", AnswerMode.ASSISTIVE)
    assert "Rispondi sempre in italiano." in system_content("it", AnswerMode.ASSISTIVE)


def test_unsupported_locale_falls_back_to_english():
    assert "Always answer in English." in system_content("fr")


def test_refusal_message_follows_the_locale():
    assert refusal_message("it").startswith("Non ho trovato")
    assert refusal_message("en").startswith("I could not find")
    assert refusal_message(None).startswith("I could not find")


def user_content(locale) -> str:
    messages = build_messages(
        "What color?", [CHUNK], answer_mode=AnswerMode.STRICT, locale=locale
    )
    return messages[-1].content


def test_english_labels_for_english_locale():
    content = user_content("en")

    assert "CONTEXT:" in content
    assert "QUESTION:" in content
    assert "CONTESTO:" not in content
    assert "DOMANDA:" not in content


def test_italian_labels_for_italian_locale():
    content = user_content("it")

    assert "CONTESTO:" in content
    assert "DOMANDA:" in content
