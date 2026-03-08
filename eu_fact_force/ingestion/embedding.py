from eu_fact_force.ingestion.models import DocumentChunk
from typing import Iterator

MODEL_ID = "intfloat/multilingual-e5-base"
# E5 models expect "passage: " for documents to index and "query: " for search queries (asymmetric retrieval).
PASSAGE_PREFIX = "passage: "
EMBED_BATCH_SIZE = 32
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_ID)
    return _MODEL


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
        DocumentChunk.objects.bulk_update(batch, ["embedding"])
