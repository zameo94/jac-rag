import threading

from app.core.config import get_settings
from app.services.rag import embeddings
from app.services.rag.embeddings import embed_query, embed_texts, embedding_dimension


async def test_embed_texts_returns_one_vector_per_text():
    vectors = await embed_texts(["ciao", "hello"])

    assert len(vectors) == 2
    assert all(isinstance(vector, list) for vector in vectors)


async def test_embed_texts_dimension_matches_config():
    vectors = await embed_texts(["dimension check"])

    assert len(vectors[0]) == embedding_dimension()


async def test_embed_texts_empty_returns_empty():
    assert await embed_texts([]) == []


async def test_embed_query_returns_single_vector():
    vector = await embed_query("domanda")

    assert len(vector) == get_settings().embedding_dim


async def test_embed_query_matches_batch_shape():
    batch = (await embed_texts(["same text"]))[0]
    single = await embed_query("same text")

    assert len(batch) == len(single)


async def test_embed_texts_runs_in_worker_thread(monkeypatch):
    thread_ids: list[int] = []

    def sync_slow(texts):
        thread_ids.append(threading.current_thread().ident)
        return [[0.0] for _ in texts]

    monkeypatch.setattr(embeddings, "_embed_texts_sync", sync_slow)

    await embeddings.embed_texts(["x", "y"])

    assert thread_ids and all(ident != threading.main_thread().ident for ident in thread_ids)


def test_embedder_is_cached():
    assert embeddings.get_embedder() is embeddings.get_embedder()


def test_embedding_dimension_reads_settings():
    assert embedding_dimension() == get_settings().embedding_dim