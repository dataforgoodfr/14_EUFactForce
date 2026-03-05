"""Tests for ingestion text chunking helpers."""

import pytest

from eu_fact_force.ingestion.chunking import split_into_paragraph_chunks


def test_split_into_paragraph_chunks_keeps_order():
    text = "alpha\n\nbeta\n\ngamma"
    assert split_into_paragraph_chunks(text, max_chunk_chars=100, overlap_chars=10) == [
        "alpha\n\nbeta\n\ngamma"
    ]


def test_split_into_paragraph_chunks_enforces_max_size():
    text = "a" * 90 + "\n\n" + "b" * 90 + "\n\n" + "c" * 90
    chunks = split_into_paragraph_chunks(text, max_chunk_chars=120, overlap_chars=20)
    assert chunks
    assert all(len(chunk) <= 120 for chunk in chunks)


def test_split_into_paragraph_chunks_ignores_empty_or_noise():
    text = "   \n\n---\n\n   \n\nreal paragraph"
    assert split_into_paragraph_chunks(text, max_chunk_chars=100, overlap_chars=10) == [
        "real paragraph"
    ]


def test_split_into_paragraph_chunks_rejects_invalid_sizes():
    with pytest.raises(ValueError):
        split_into_paragraph_chunks("text", max_chunk_chars=100, overlap_chars=100)
