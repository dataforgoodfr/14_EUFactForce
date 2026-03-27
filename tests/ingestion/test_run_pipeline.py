"""Tests for the ingestion pipeline using the project README.md as test file."""

from pathlib import Path
from unittest.mock import patch

import pytest

from eu_fact_force.ingestion.models import (EMBEDDING_DIMENSIONS,
                                            DocumentChunk, SourceFile)
from eu_fact_force.ingestion.services import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]

@patch("eu_fact_force.ingestion.services.fetch_file_and_metadata", return_value=(PROJECT_ROOT / "tests/ingestion/fixtures/jhab032.pdf", ["test"]))
@pytest.mark.django_db
def test_run_pipeline_uses_readme_md(tmp_storage, monkeypatch):
    """Run the full pipeline with the project README.md as the test file."""
    source_file, _ = run_pipeline("test/doi")

    assert source_file is not None
    assert source_file.doi == "test/doi"
    assert source_file.status == SourceFile.Status.PARSED
    assert source_file.s3_key == 'ingestion/sources/jhab032.pdf'

    assert (tmp_storage / "ingestion" / "sources" / "jhab032.pdf").exists()

    saved_chunks = list(
        DocumentChunk.objects.filter(source_file=source_file).order_by("order")
    )
    assert len(saved_chunks) == 73
    with open(PROJECT_ROOT / "tests/ingestion/fixtures/jhab032_first_chunk.txt") as f:
        first_content = f.read()
    assert saved_chunks[0].content == first_content
    assert len(saved_chunks[0].embedding) == EMBEDDING_DIMENSIONS
