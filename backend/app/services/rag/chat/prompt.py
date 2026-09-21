from __future__ import annotations

from app.schemas.tenant import AnswerMode
from app.services.llm.base import LLMMessage, LLMRole
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
        "Cita le fonti con [n]. Rispondi nella lingua della domanda. Quando la "
        "domanda indica un periodo o un documento (es. \"febbraio 22\"), usa SOLO "
        "i passaggi di quel documento e ignora valori simili di altri periodi. "
        "Se la domanda chiede un massimo, un minimo o un confronto, esamina TUTTE "
        "le opzioni presenti nel contesto e indica quella con i valori richiesti, "
        "citando il codice o l'etichetta."
    ),
    "en": (
        "Answer using only the provided CONTEXT. If the context does not contain "
        "the answer, say that you do not know. Do not make up information. Cite "
        "sources as [n]. Answer in the language of the question. When the question "
        "names a period or document (e.g. \"February 22\"), use ONLY the passages "
        "from that document and ignore similar values from other periods. If the "
        "question asks for a maximum, minimum or a comparison, review ALL options "
        "in the context and report the one with the requested values, citing the "
        "code or label."
    ),
}

SYSTEM_ASSISTIVE = {
    "it": (
        "Rispondi in modo utile. Se è presente un CONTESTO, privilegialo e citalo "
        "con [n]. Rispondi nella lingua della domanda. Quando la domanda indica un "
        "periodo o un documento, usa SOLO i passaggi di quel documento. Per "
        "massimi, minimi o confronti, esamina tutte le opzioni del contesto."
    ),
    "en": (
        "Answer helpfully. If a CONTEXT is present, prefer it and cite it as [n]. "
        "Answer in the language of the question. When the question names a period "
        "or document, use ONLY the passages from that document. For maximums, "
        "minimums or comparisons, review all options in the context."
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
