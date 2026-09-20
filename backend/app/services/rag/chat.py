from __future__ import annotations

from app.schemas.tenant import AnswerMode
from app.services.llm.base import LLMMessage, LLMProvider, LLMRole
from app.services.rag.vector_store import RetrievedChunk

SUPPORTED_LOCALES = ("it", "en")
FALLBACK_LOCALE = "it"

REFUSALS = {
    "it": "Non ho trovato questa informazione nei documenti disponibili.",
    "en": "I could not find this information in the available documents.",
}

SYSTEM_STRICT = {
    "it": (
        "Rispondi esclusivamente usando il CONTESTO fornito. Se il contesto non "
        "contiene la risposta, dì che non lo sai. Non inventare informazioni. "
        "Cita le fonti con [n]. Rispondi nella lingua della domanda."
    ),
    "en": (
        "Answer using only the provided CONTEXT. If the context does not contain "
        "the answer, say that you do not know. Do not make up information. Cite "
        "sources as [n]. Answer in the language of the question."
    ),
}

SYSTEM_ASSISTIVE = {
    "it": (
        "Rispondi in modo utile. Se è presente un CONTESTO, privilegialo e citalo "
        "con [n]. Rispondi nella lingua della domanda."
    ),
    "en": (
        "Answer helpfully. If a CONTEXT is present, prefer it and cite it as [n]. "
        "Answer in the language of the question."
    ),
}


def resolve_locale(locale: str | None) -> str:
    return locale if locale in SUPPORTED_LOCALES else FALLBACK_LOCALE


def refusal_message(locale: str | None) -> str:
    return REFUSALS[resolve_locale(locale)]


def build_messages(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    answer_mode: AnswerMode,
    locale: str | None,
) -> list[LLMMessage]:
    resolved = resolve_locale(locale)
    if chunks:
        system = (
            SYSTEM_STRICT[resolved]
            if answer_mode is AnswerMode.STRICT
            else SYSTEM_ASSISTIVE[resolved]
        )
        context = "\n".join(
            f"[{position}] {chunk.filename} (chunk {chunk.chunk_index}): {chunk.text}"
            for position, chunk in enumerate(chunks, start=1)
        )
        user_content = f"CONTESTO:\n{context}\n\nDOMANDA: {question}"
    else:
        system = SYSTEM_ASSISTIVE[resolved]
        user_content = question
    return [
        LLMMessage(role=LLMRole.SYSTEM, content=system),
        LLMMessage(role=LLMRole.USER, content=user_content),
    ]


async def generate_reply(
    provider: LLMProvider,
    question: str,
    chunks: list[RetrievedChunk],
    *,
    answer_mode: AnswerMode,
    locale: str | None,
) -> tuple[str, list[RetrievedChunk]]:
    """Generate one reply with the single selected provider.

    In strict mode with no grounded context the refusal is deterministic and the
    provider is not called. ``chunks`` are only the chunks actually used.
    """
    if answer_mode is AnswerMode.STRICT and not chunks:
        return refusal_message(locale), []
    response = await provider.generate(
        build_messages(question, chunks, answer_mode=answer_mode, locale=locale)
    )
    return response.content, list(chunks)
