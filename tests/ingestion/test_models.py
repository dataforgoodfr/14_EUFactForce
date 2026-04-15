"""Tests for ingestion models: constraints, cascade behaviour, and relationships."""

from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import IntegrityError

from eu_fact_force.ingestion.models import Document, DocumentChunk, SourceFile
from tests.factories import DocumentChunkFactory, DocumentFactory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"


@pytest.mark.django_db
def test_deleting_source_file_removes_file_from_storage(tmp_path, tmp_storage):
    """
    When a SourceFile is deleted, the corresponding file is removed from storage.
    Uses the pipeline to create a SourceFile with a real file in storage.
    """
    fn = tmp_path / "test_file.txt"
    with fn.open("w") as f:
        f.write("test content")

    inp = SourceFile.create_from_file(fn, doi="test_doi")
    s3_fn = tmp_storage / inp.s3_key
    assert s3_fn.exists()
    inp.delete()
    assert not s3_fn.exists()


# --- Document: title constraint ---


@pytest.mark.django_db
def test_document_requires_title():
    """Document.title is non-null and non-blank at the DB level."""
    with pytest.raises(IntegrityError):
        Document.objects.create(title=None)


@pytest.mark.django_db
def test_document_created_with_title():
    """A Document with a valid title is persisted."""
    doc = Document.objects.create(title="Climate change and health")
    assert doc.pk is not None
    assert doc.title == "Climate change and health"


# --- Document: DOI uniqueness ---


@pytest.mark.django_db
def test_duplicate_nonempty_doi_rejected():
    """Two Documents with the same non-empty DOI raise IntegrityError."""
    Document.objects.create(title="Paper A", doi="10.1234/abc")
    with pytest.raises(IntegrityError):
        Document.objects.create(title="Paper B", doi="10.1234/abc")


@pytest.mark.django_db
def test_multiple_documents_without_doi_allowed():
    """Multiple Documents with empty DOI are allowed (partial unique constraint)."""
    Document.objects.create(title="Report A", doi="")
    Document.objects.create(title="Report B", doi="")
    assert Document.objects.filter(doi="").count() == 2


# --- Document: metadata-only state (no SourceFile) ---


@pytest.mark.django_db
def test_document_created_without_source_file():
    """A Document can exist without a linked SourceFile."""
    doc = Document.objects.create(title="Metadata-only paper", doi="10.9999/meta")
    assert doc.pk is not None


# --- DocumentChunk: requires Document ---


@pytest.mark.django_db
def test_document_chunk_requires_document():
    """DocumentChunk cannot be created without a Document FK."""
    with pytest.raises(IntegrityError):
        DocumentChunk.objects.create(
            document=None,
            content="Some text",
            order=1,
        )


@pytest.mark.django_db
def test_document_chunk_linked_to_document():
    """DocumentChunk is accessible via Document.chunks."""
    chunk = DocumentChunkFactory()
    assert chunk.document is not None
    assert chunk in chunk.document.chunks.all()
