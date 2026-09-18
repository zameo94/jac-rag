from app.services.rag.language import detect_language


def test_detect_language_italian():
    text = "Questo è un documento scritto in italiano con molte parole comuni."

    assert detect_language(text) == "it"


def test_detect_language_english():
    text = "This is a document written in English with many common words inside."

    assert detect_language(text) == "en"


def test_detect_language_returns_none_for_short_text():
    assert detect_language("ciao") is None


def test_detect_language_returns_none_for_blank_text():
    assert detect_language("   ") is None


def test_detect_language_returns_unsupported_language_code():
    text = "Ceci est un document écrit en français avec beaucoup de mots communs."

    assert detect_language(text) == "fr"
