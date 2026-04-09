"""Semantic search over ingested document chunks using pgvector."""

from pathlib import Path

from pgvector.django import CosineDistance

from eu_fact_force.ingestion.embedding import embed_query
from eu_fact_force.ingestion.models import DocumentChunk

_PROMPTS_DIR = Path(__file__).resolve().parent / "data_collection" / "prompts"


class NarrativeNotFoundError(FileNotFoundError):
    """No prompts/<narrative>.md for the given narrative keyword."""


def list_prompt_keywords() -> list[str]:
    """Basenames of narrative prompts (one .md file per keyword), sorted."""
    return sorted(p.stem for p in _PROMPTS_DIR.glob("*.md"))


def search_chunks(query: str, k: int = 10) -> list[tuple[DocumentChunk, float]]:
    """
    Return the top-k document chunks most similar to the query.

    The query is embedded with the same model as ingestion (E5, query prefix).
    Results are ordered by cosine distance (lower is more similar).
    Only chunks with a stored embedding are considered.

    Returns a list of (chunk, distance) tuples. Chunk includes source_file
    via the ORM relation for display (e.g. source_file.doi).
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")
    query_vector = embed_query(query)
    qs = (
        DocumentChunk.objects.filter(embedding__isnull=False)
        .select_related("source_file")
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:k]
    )
    return [(chunk, float(chunk.distance)) for chunk in qs]


def search_narrative(narrative: str, k: int = 10) -> list[tuple[DocumentChunk, float]]:
    prompt = _PROMPTS_DIR / f"{narrative}.md"
    if not prompt.exists():
        raise NarrativeNotFoundError(f"Prompt file not found: {prompt}")
    return search_chunks(prompt.read_text(), k)


def chunks_context(top_chunks: list[tuple[DocumentChunk, float]]) -> dict:
    chunks = [
        {
            "type": "text",
            "content": chunk.content,
            "score": score,
            "metadata": {"document_id": chunk.source_file.id, "page": -1},
        }
        for chunk, score in top_chunks
    ]

    documents = {}
    for chunk, _ in top_chunks:
        source_file = chunk.source_file
        if source_file.id in documents:
            continue
        meta = source_file.metadata
        documents[source_file.id] = {
            "id": source_file.id,
            "doi": source_file.doi,
            "tags_pubmed": meta.tags_pubmed,
        }
    return {
        "chunks": chunks,
        "documents": documents,
    }
