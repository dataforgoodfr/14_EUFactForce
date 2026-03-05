"""Tests for ingestion embedding persistence."""

import pytest

from eu_fact_force.ingestion import embedding as embedding_module
from eu_fact_force.ingestion.models import DocumentChunk, SourceFile


class _FakeModel:
    def __init__(self):
        self.calls: list[list[str]] = []

    def encode(self, texts, show_progress_bar, normalize_embeddings):
        self.calls.append(list(texts))
        return [[0.1] * 768 for _ in texts]


@pytest.mark.django_db
def test_add_embeddings_updates_persisted_chunks(monkeypatch):
    source = SourceFile.objects.create(doi="x", s3_key="k", status=SourceFile.Status.STORED)
    chunk_1 = DocumentChunk.objects.create(source_file=source, content="alpha", order=1)
    chunk_2 = DocumentChunk.objects.create(source_file=source, content="beta", order=2)

    fake_model = _FakeModel()
    monkeypatch.setattr(embedding_module, "_get_model", lambda: fake_model)

    embedding_module.add_embeddings([chunk_1, chunk_2])

    chunk_1.refresh_from_db()
    chunk_2.refresh_from_db()
    assert len(chunk_1.embedding) == 768
    assert len(chunk_2.embedding) == 768
    assert chunk_1.embedding[0] == pytest.approx(0.1)
    assert chunk_2.embedding[0] == pytest.approx(0.1)
    assert fake_model.calls == [["passage: alpha", "passage: beta"]]


@pytest.mark.django_db
def test_add_embeddings_skips_unsaved_and_empty_chunks(monkeypatch):
    source = SourceFile.objects.create(doi="x", s3_key="k", status=SourceFile.Status.STORED)
    persisted = DocumentChunk.objects.create(source_file=source, content="ok", order=1)
    empty_chunk = DocumentChunk(source_file=source, content="   ", order=2)
    unsaved_chunk = DocumentChunk(source_file=source, content="temp", order=3)

    fake_model = _FakeModel()
    monkeypatch.setattr(embedding_module, "_get_model", lambda: fake_model)

    embedding_module.add_embeddings([persisted, empty_chunk, unsaved_chunk])

    persisted.refresh_from_db()
    assert len(persisted.embedding) == 768
    assert persisted.embedding[0] == pytest.approx(0.1)
    assert fake_model.calls == [["passage: ok"]]
