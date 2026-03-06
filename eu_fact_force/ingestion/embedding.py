from eu_fact_force.ingestion.models import DocumentChunk
from typing import Iterator

MODEL_ID = "intfloat/multilingual-e5-base"
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "
EMBED_BATCH_SIZE = 32
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_ID)
    return _MODEL


def embed_query(query: str) -> list[float]:
    """
    Embed a search query with the same model as ingestion (E5 query prefix).
    Returns a 768-d normalized vector for use with pgvector similarity search.
    """
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    model = _get_model()
    text = f"{QUERY_PREFIX}{query.strip()}"
    vector = model.encode(
        [text],
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    out = vector[0]
    return out.tolist() if hasattr(out, "tolist") else list(out)


def _iter_batches(items: list[DocumentChunk], batch_size: int) -> Iterator[list[DocumentChunk]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def add_embeddings(chunks: list[DocumentChunk]):
    """
    Add embeddings to the chunks and update in the DB.
    """
    persisted_chunks = [
        chunk for chunk in chunks if chunk.pk is not None and chunk.content.strip()
    ]
    if not persisted_chunks:
        return

    model = _get_model()
    for batch in _iter_batches(persisted_chunks, EMBED_BATCH_SIZE):
        texts = [f"{PASSAGE_PREFIX}{chunk.content}" for chunk in batch]
        vectors = model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector.tolist() if hasattr(vector, "tolist") else list(vector)

    DocumentChunk.objects.bulk_update(persisted_chunks, ["embedding"])
