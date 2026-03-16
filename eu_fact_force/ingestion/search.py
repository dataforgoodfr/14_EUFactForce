"""Semantic search over ingested document chunks using pgvector."""

from __future__ import annotations

from eu_fact_force.ingestion.embedding import embed_query
from eu_fact_force.ingestion.models import DocumentChunk
from pgvector.django import CosineDistance


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
