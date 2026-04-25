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
from tests.factories import AuthorFactory, DocumentChunkFactory, DocumentFactory

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

        doc = DocumentFactory()
        # Query [1,0,...,0]: closest to chunk_near (same), then chunk_far ([0,1,0,...,0]).
        chunk_far = DocumentChunkFactory(
            document=doc, content="far", embedding=_one_hot_vector(1)
        )
        chunk_near = DocumentChunkFactory(
            document=doc, content="near", embedding=_one_hot_vector(0)
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

        doc = DocumentFactory()
        with_emb = DocumentChunkFactory(
            document=doc, content="with", embedding=_constant_vector(0.1)
        )
        DocumentChunkFactory(document=doc, content="without", embedding=None)

        results = search_module.search_chunks("q", k=5)

        assert len(results) == 1
        assert results[0][0].content == "with"
        assert results[0][0].pk == with_emb.pk

    @pytest.mark.django_db
    @patch("eu_fact_force.ingestion.search.embed_query")
    def test_respects_k(self, mock_embed_query):
        """At most k results are returned."""
        mock_embed_query.side_effect = lambda _: _constant_vector(0.5)

        doc = DocumentFactory()
        for _ in range(5):
            DocumentChunkFactory(
                document=doc,
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

        doc = DocumentFactory()

        same = DocumentChunkFactory(
            document=doc, embedding=_rank2_in_full_space(1.0, 0.0)
        )
        near = DocumentChunkFactory(
            document=doc, embedding=_rank2_in_full_space(0.99, 0.01)
        )
        far = DocumentChunkFactory(
            document=doc, embedding=_rank2_in_full_space(0.0, 1.0)
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
        assert all(r[0].document_id == doc.pk for r in results)


@pytest.mark.django_db
class TestChunksContext:
    def test_empty_top_chunks(self):
        assert chunks_context([]) == {"chunks": [], "documents": {}, "authors": {}}

    def test_two_chunks_single_document(self):
        doc = DocumentFactory(doi="doi/single")
        chunk_a = DocumentChunkFactory(document=doc, content="first")
        chunk_b = DocumentChunkFactory(document=doc, content="second")

        result = chunks_context([(chunk_a, 0.9), (chunk_b, 0.8)])

        assert result["chunks"] == [
            {
                "type": "text",
                "content": "first",
                "score": 0.9,
                "metadata": {"document_id": doc.id, "page": -1},
            },
            {
                "type": "text",
                "content": "second",
                "score": 0.8,
                "metadata": {"document_id": doc.id, "page": -1},
            },
        ]
        assert result["documents"] == {
            doc.id: {
                "id": doc.id,
                "doi": "doi/single",
                "title": doc.title,
                "keywords": [],
                "author_ids": [],
            }
        }

    def test_two_chunks_two_documents(self):
        doc1 = DocumentFactory(doi="doi/one")
        doc2 = DocumentFactory(doi="doi/two")

        c1 = DocumentChunkFactory(document=doc1, content="alpha", order=0)
        c2 = DocumentChunkFactory(document=doc2, content="beta", order=0)

        result = chunks_context([(c1, 0.1), (c2, 0.2)])

        assert [x["content"] for x in result["chunks"]] == ["alpha", "beta"]
        assert result["documents"] == {
            doc1.id: {
                "id": doc1.id,
                "doi": "doi/one",
                "title": doc1.title,
                "keywords": [],
                "author_ids": [],
            },
            doc2.id: {
                "id": doc2.id,
                "doi": "doi/two",
                "title": doc2.title,
                "keywords": [],
                "author_ids": [],
            },
        }

    def test_chunks_with_authors_and_keywords(self):
        author = AuthorFactory(full_name="Emmy Noether", orcid="0000-0001-5000-0007")
        doc = DocumentFactory(doi="doi/test", keywords=["vaccine", "autism"])
        doc.authors.add(author)
        chunk = DocumentChunkFactory(document=doc, content="text")

        result = chunks_context([(chunk, 0.9)])

        assert result["documents"][doc.id]["keywords"] == ["vaccine", "autism"]
        assert result["documents"][doc.id]["author_ids"] == [str(author.id)]
        assert result["authors"] == {
            str(author.id): {"name": "Emmy Noether", "orcid": "0000-0001-5000-0007"}
        }
