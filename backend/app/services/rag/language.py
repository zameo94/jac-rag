from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {"it", "en"}


def detect_language(text: str) -> str | None:
    sample = text.strip()
    if len(sample) < 20:
        return None
    try:
        language = detect(sample[:2000])
    except LangDetectException:
        return None
    if language not in SUPPORTED_LANGUAGES:
        return language
    return language
