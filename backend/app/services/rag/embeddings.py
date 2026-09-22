import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings

_embed_semaphore = asyncio.Semaphore(2)


@lru_cache
def get_embedder() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(model_name=settings.embedding_model)


def _embed_texts_sync(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = get_embedder()
    return [vector.tolist() for vector in embedder.embed(texts)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed in a worker thread so fastembed never blocks the event loop."""
    if not texts:
        return []
    async with _embed_semaphore:
        return await asyncio.to_thread(_embed_texts_sync, texts)


async def embed_query(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0]


def embedding_dimension() -> int:
    return get_settings().embedding_dim
