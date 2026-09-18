from app.core.config import get_settings
from app.services.rag import embeddings
from app.services.rag.embeddings import embed_query, embed_texts, embedding_dimension


def test_embed_texts_returns_one_vector_per_text():
    vectors = embed_texts(["ciao", "hello"])

    assert len(vectors) == 2
    assert all(isinstance(vector, list) for vector in vectors)


def test_embed_texts_dimension_matches_config():
    vectors = embed_texts(["dimension check"])

    assert len(vectors[0]) == embedding_dimension()


def test_embed_texts_empty_returns_empty():
    assert embed_texts([]) == []


def test_embed_query_returns_single_vector():
    vector = embed_query("domanda")

    assert len(vector) == get_settings().embedding_dim


def test_embed_query_matches_batch_shape():
    batch = embed_texts(["same text"])[0]
    single = embed_query("same text")

    assert len(batch) == len(single)


def test_embedder_is_cached():
    assert embeddings.get_embedder() is embeddings.get_embedder()


def test_embedding_dimension_reads_settings():
    assert embedding_dimension() == get_settings().embedding_dim
