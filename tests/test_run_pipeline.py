"""Tests for the ingestion pipeline using the project README.md as test file."""

from pathlib import Path

import pytest

from eu_fact_force.ingestion.models import DocumentChunk, SourceFile
from eu_fact_force.ingestion.services import run_pipeline

# Central README.md path (project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"

# V0: chunks come from tags_pubmed = ["simulated", doi]
EXPECTED_CHUNK_CONTENTS = ["simulated", "README.md"]


@pytest.mark.django_db
def test_run_pipeline_uses_readme_md(tmp_storage):
    """Run the full pipeline with the project README.md as the test file."""
    assert README_PATH.exists(), f"Test file must exist: {README_PATH}"

    source_file, _ = run_pipeline("README.md")

    assert source_file is not None
    assert source_file.doi == "README.md"
    assert source_file.status == SourceFile.Status.PARSED
    assert "README.md" in source_file.s3_key

    assert (tmp_storage / "ingestion" / "sources" / "README.md").exists()

    saved_chunks = list(
        DocumentChunk.objects.filter(source_file=source_file).order_by("order")
    )
    saved_chunk_contents = [chunk.content for chunk in saved_chunks]
    assert saved_chunk_contents == ["simulated", "README.md"]
