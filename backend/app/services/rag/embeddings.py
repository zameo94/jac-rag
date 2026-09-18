from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings


@lru_cache
def get_embedder() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(model_name=settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = get_embedder()
    return [vector.tolist() for vector in embedder.embed(texts)]


def embed_query(text: str) -> list[float]:
    vectors = embed_texts([text])
    return vectors[0]


def embedding_dimension() -> int:
    return get_settings().embedding_dim
