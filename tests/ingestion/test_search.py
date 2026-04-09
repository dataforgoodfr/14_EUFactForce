"""Tests for semantic search over document chunks."""

from pathlib import Path
from unittest.mock import patch

import pytest

from eu_fact_force.ingestion import models as ingestion_models
from eu_fact_force.ingestion import search as search_module
from eu_fact_force.ingestion.chunking import MAX_CHUNK_CHARS
from eu_fact_force.ingestion.models import (
    EMBEDDING_DIMENSIONS,
    DocumentChunk,
)
from eu_fact_force.ingestion.search import chunks_context
from tests.factories import DocumentChunkFactory, FileMetadataFactory, SourceFileFactory

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Tolerance for float distance comparison.
DISTANCE_TOLERANCE = 1e-5
# Paragraph length so chunking yields 3 separate chunks (each under MAX_CHUNK_CHARS).
PARAGRAPH_LEN = (MAX_CHUNK_CHARS // 2) + 1
# Components for the second-closest vector (distance between near and far).
SECOND_CLOSEST_VEC_ALIGNED = 0.99
SECOND_CLOSEST_VEC_OFF = 0.01


def _constant_vector(value: float, dim: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Vector with the same value in every dimension."""
    return [value] * dim


def _one_hot_vector(index: int, dim: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """One-hot vector: 1.0 at index, 0 elsewhere (for distinct cosine distances)."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


class TestSearchChunks:
    @pytest.mark.django_db
    @patch("eu_fact_force.ingestion.search.embed_query")
    def test_returns_chunks_ordered_by_distance(self, mock_embed_query):
        """search_chunks returns (chunk, distance) tuples ordered by cosine distance."""
        mock_embed_query.side_effect = lambda _: _one_hot_vector(0)

        source = SourceFileFactory()
        # Query [1,0,...,0]: closest to chunk_near (same), then chunk_far ([0,1,0,...,0]).
        chunk_far = DocumentChunkFactory(
            source_file=source, content="far", embedding=_one_hot_vector(1)
        )
        chunk_near = DocumentChunkFactory(
            source_file=source, content="near", embedding=_one_hot_vector(0)
        )

        results = search_module.search_chunks("dummy", k=5)

        assert len(results) == 2
        (first, d1), (second, d2) = results
        assert first.content == "near"
        assert first.pk == chunk_near.pk
        assert second.content == "far"
        assert second.pk == chunk_far.pk
        assert d1 == pytest.approx(0.0, abs=DISTANCE_TOLERANCE)
        assert d2 > 0

    @pytest.mark.django_db
    @patch("eu_fact_force.ingestion.search.embed_query")
    def test_excludes_chunks_without_embedding(self, mock_embed_query):
        """Only chunks with a stored embedding are returned."""
        mock_embed_query.side_effect = lambda _: _constant_vector(0.1)

        source = SourceFileFactory()
        with_emb = DocumentChunkFactory(
            source_file=source, content="with", embedding=_constant_vector(0.1)
        )
        DocumentChunkFactory(source_file=source, content="without", embedding=None)

        results = search_module.search_chunks("q", k=5)

        assert len(results) == 1
        assert results[0][0].content == "with"
        assert results[0][0].pk == with_emb.pk

    @pytest.mark.django_db
    @patch("eu_fact_force.ingestion.search.embed_query")
    def test_respects_k(self, mock_embed_query):
        """At most k results are returned."""
        mock_embed_query.side_effect = lambda _: _constant_vector(0.5)

        source = SourceFileFactory()
        for _ in range(5):
            DocumentChunkFactory(
                source_file=source,
                embedding=_constant_vector(0.5),
            )

        assert len(search_module.search_chunks("q", k=2)) == 2
        assert len(search_module.search_chunks("q", k=10)) == 5

    @pytest.mark.django_db
    def test_k_zero_raises_value_error(self):
        """k<=0 raises ValueError to signal incorrect usage."""
        with pytest.raises(ValueError):
            search_module.search_chunks("q", k=0)

    @pytest.mark.django_db
    @patch("eu_fact_force.ingestion.search.embed_query")
    @patch("eu_fact_force.ingestion.models.EMBEDDING_DIMENSIONS", 2)
    def test_pipeline_then_search_returns_chunks_ordered_by_similarity(
        self, mock_embed_query
    ):
        """Three chunks in DB (factories); search order follows cosine distance in rank-2."""
        full_dim = DocumentChunk._meta.get_field("embedding").dimensions
        rank_dim = ingestion_models.EMBEDDING_DIMENSIONS

        def _rank2_in_full_space(x: float, y: float) -> list[float]:
            return [x, y] + [0.0] * (full_dim - rank_dim)

        source_file = SourceFileFactory()

        same = DocumentChunkFactory(
            source_file=source_file, embedding=_rank2_in_full_space(1.0, 0.0)
        )
        near = DocumentChunkFactory(
            source_file=source_file, embedding=_rank2_in_full_space(0.99, 0.01)
        )
        far = DocumentChunkFactory(
            source_file=source_file, embedding=_rank2_in_full_space(0.0, 1.0)
        )

        mock_embed_query.side_effect = lambda _: _rank2_in_full_space(1.0, 0.0)
        results = search_module.search_chunks("query", k=5)

        contents = [r[0].content for r in results]
        assert contents == [same.content, near.content, far.content]
        similarities = [r[1] for r in results]
        assert similarities == [
            0.0,
            pytest.approx(5.1e-5, abs=1e-6),
            pytest.approx(1.0),
        ]
        assert all(r[0].source_file_id == source_file.pk for r in results)


@pytest.mark.django_db
class TestChunksContext:
    def test_empty_top_chunks(self):
        assert chunks_context([]) == {"chunks": [], "documents": {}}

    def test_two_chunks_single_source_file(self):
        source = SourceFileFactory(doi="doi/single", s3_key="key/single")
        FileMetadataFactory(source_file=source, tags_pubmed=["mesh:a"])
        chunk_a = DocumentChunkFactory(source_file=source, content="first")
        chunk_b = DocumentChunkFactory(source_file=source, content="second")

        result = chunks_context([(chunk_a, 0.9), (chunk_b, 0.8)])

        assert result["chunks"] == [
            {
                "type": "text",
                "content": "first",
                "score": 0.9,
                "metadata": {"document_id": source.id, "page": -1},
            },
            {
                "type": "text",
                "content": "second",
                "score": 0.8,
                "metadata": {"document_id": source.id, "page": -1},
            },
        ]
        assert result["documents"] == {
            source.id: {
                "id": source.id,
                "doi": "doi/single",
                "tags_pubmed": ["mesh:a"],
            }
        }

    def test_two_chunks_two_source_files(self):
        src1 = SourceFileFactory(doi="doi/one", s3_key="k1")
        FileMetadataFactory(source_file=src1, tags_pubmed=["t1"])
        src2 = SourceFileFactory(doi="doi/two", s3_key="k2")
        FileMetadataFactory(source_file=src2, tags_pubmed=["t2", "t3"])

        c1 = DocumentChunkFactory(source_file=src1, content="alpha", order=0)
        c2 = DocumentChunkFactory(source_file=src2, content="beta", order=0)

        result = chunks_context([(c1, 0.1), (c2, 0.2)])

        assert [x["content"] for x in result["chunks"]] == ["alpha", "beta"]
        assert result["documents"] == {
            src1.id: {"id": src1.id, "doi": "doi/one", "tags_pubmed": ["t1"]},
            src2.id: {"id": src2.id, "doi": "doi/two", "tags_pubmed": ["t2", "t3"]},
        }
