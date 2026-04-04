"""Tests for semantic search over document chunks."""

from pathlib import Path

import pytest

from eu_fact_force.ingestion import parsing as parsing_module
from eu_fact_force.ingestion import search as search_module
from eu_fact_force.ingestion import services as services_module
from eu_fact_force.ingestion.chunking import MAX_CHUNK_CHARS
from eu_fact_force.ingestion.models import (
    EMBEDDING_DIMENSIONS,
    DocumentChunk,
    SourceFile,
)
from eu_fact_force.ingestion.search import chunks_context
from eu_fact_force.ingestion.services import run_pipeline
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
    def test_returns_chunks_ordered_by_distance(self, monkeypatch):
        """search_chunks returns (chunk, distance) tuples ordered by cosine distance."""
        source = SourceFile.objects.create(
            doi="d", s3_key="k", status=SourceFile.Status.STORED
        )
        # Query [1,0,...,0]: closest to chunk_near (same), then chunk_far ([0,1,0,...,0]).
        chunk_far = DocumentChunk.objects.create(
            source_file=source, content="far", order=1, embedding=_one_hot_vector(1)
        )
        chunk_near = DocumentChunk.objects.create(
            source_file=source, content="near", order=2, embedding=_one_hot_vector(0)
        )

        monkeypatch.setattr(search_module, "embed_query", lambda _: _one_hot_vector(0))

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
    def test_excludes_chunks_without_embedding(self, monkeypatch):
        """Only chunks with a stored embedding are returned."""
        source = SourceFile.objects.create(
            doi="d", s3_key="k", status=SourceFile.Status.STORED
        )
        with_emb = DocumentChunk.objects.create(
            source_file=source, content="with", order=1, embedding=_constant_vector(0.1)
        )
        DocumentChunk.objects.create(
            source_file=source, content="without", order=2, embedding=None
        )

        monkeypatch.setattr(
            search_module, "embed_query", lambda _: _constant_vector(0.1)
        )

        results = search_module.search_chunks("q", k=5)

        assert len(results) == 1
        assert results[0][0].content == "with"
        assert results[0][0].pk == with_emb.pk

    @pytest.mark.django_db
    def test_respects_k(self, monkeypatch):
        """At most k results are returned."""
        source = SourceFile.objects.create(
            doi="d", s3_key="k", status=SourceFile.Status.STORED
        )
        for i in range(5):
            DocumentChunk.objects.create(
                source_file=source,
                content=f"c{i}",
                order=i,
                embedding=_constant_vector(0.5),
            )

        monkeypatch.setattr(
            search_module, "embed_query", lambda _: _constant_vector(0.5)
        )

        assert len(search_module.search_chunks("q", k=2)) == 2
        assert len(search_module.search_chunks("q", k=10)) == 5

    @pytest.mark.django_db
    def test_k_zero_raises_value_error(self):
        """k<=0 raises ValueError to signal incorrect usage."""
        with pytest.raises(ValueError):
            search_module.search_chunks("q", k=0)

    @pytest.mark.django_db
    def test_pipeline_then_search_returns_chunks_ordered_by_similarity(
        self, tmp_storage, monkeypatch
    ):
        """Run pipeline with mocked parse and add_embeddings, then search; order matches."""
        readme_fn = PROJECT_ROOT / "README.md"
        assert readme_fn.exists(), f"Test file must exist: {readme_fn}"

        # Long enough so paragraph chunking produces three separate chunks (max_chunk_chars=1200).
        p1, p2, p3 = "A" * PARAGRAPH_LEN, "B" * PARAGRAPH_LEN, "C" * PARAGRAPH_LEN
        parsed_text = f"{p1}\n\n{p2}\n\n{p3}"
        monkeypatch.setattr(
            parsing_module,
            "_extract_text_from_source_file",
            lambda _: parsed_text,
        )

        # Vectors so cosine distance order is well-defined: p1 closest, then p2, then p3.
        def _add_known_embeddings(chunks):
            near = _one_hot_vector(0)
            mid = (
                [SECOND_CLOSEST_VEC_ALIGNED]
                + [SECOND_CLOSEST_VEC_OFF]
                + [0.0] * (EMBEDDING_DIMENSIONS - 2)
            )
            far = _one_hot_vector(1)
            vecs = [near, mid, far]
            for i, ch in enumerate(chunks):
                if ch.pk and ch.content.strip() and i < len(vecs):
                    ch.embedding = vecs[i]
            DocumentChunk.objects.bulk_update(chunks, ["embedding"])

        monkeypatch.setattr(services_module, "add_embeddings", _add_known_embeddings)
        monkeypatch.setattr(search_module, "embed_query", lambda _: _one_hot_vector(0))

        source_file, _ = run_pipeline("README.md")
        results = search_module.search_chunks("query", k=5)

        contents = [r[0].content for r in results]
        assert contents == [p1, p2, p3]
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
