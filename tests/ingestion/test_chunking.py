"""Tests for ingestion text chunking helpers."""

import pytest

from eu_fact_force.ingestion.chunking import split_into_paragraph_chunks


class TestSplitIntoParagraphChunks:
    """Tests for split_into_paragraph_chunks."""

    def test_keeps_order(self):
        """Order of chunks matches order of paragraphs; multiple chunks when limit is small."""
        text = "alpha\n\nbeta\n\ngamma"
        # Force separate chunks so we can assert order
        chunks = split_into_paragraph_chunks(
            text, max_chunk_chars=10, overlap_chars=0
        )
        assert chunks == ["alpha", "beta", "gamma"]

    def test_merges_paragraphs_when_under_limit(self):
        """When all paragraphs fit in one chunk, they are merged."""
        text = "alpha\n\nbeta\n\ngamma"
        assert split_into_paragraph_chunks(
            text, max_chunk_chars=100, overlap_chars=10
        ) == ["alpha\n\nbeta\n\ngamma"]

    def test_enforces_max_size(self):
        text = "a" * 90 + "\n\n" + "b" * 90 + "\n\n" + "c" * 90
        chunks = split_into_paragraph_chunks(
            text, max_chunk_chars=120, overlap_chars=20
        )
        assert chunks
        assert all(len(chunk) <= 120 for chunk in chunks)

    def test_ignores_empty_or_noise(self):
        text = "   \n\n---\n\n   \n\nreal paragraph"
        assert split_into_paragraph_chunks(
            text, max_chunk_chars=100, overlap_chars=10
        ) == ["real paragraph"]

    def test_rejects_invalid_sizes(self):
        with pytest.raises(ValueError):
            split_into_paragraph_chunks(
                "text", max_chunk_chars=100, overlap_chars=100
            )
