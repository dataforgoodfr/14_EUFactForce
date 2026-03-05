"""Tests for the ingestion pipeline using the project README.md as test file."""

from pathlib import Path

import pytest

from eu_fact_force.ingestion import parsing as parsing_module
from eu_fact_force.ingestion import services as services_module
from eu_fact_force.ingestion.models import DocumentChunk, SourceFile
from eu_fact_force.ingestion.services import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_run_pipeline_uses_readme_md(tmp_storage, monkeypatch):
    """Run the full pipeline with the project README.md as the test file."""
    readme_fn = PROJECT_ROOT / "README.md"
    assert readme_fn.exists(), f"Test file must exist: {readme_fn}"

    paragraph_1 = "A" * 700
    paragraph_2 = "B" * 700
    paragraph_3 = "C" * 700
    parsed_text = f"{paragraph_1}\n\n{paragraph_2}\n\n{paragraph_3}"

    monkeypatch.setattr(
        parsing_module,
        "_extract_text_from_source_file",
        lambda _: parsed_text,
    )
    embedding_calls: list[list[str]] = []

    def _capture_embeddings(chunks):
        embedding_calls.append([chunk.content for chunk in chunks])

    monkeypatch.setattr(services_module, "add_embeddings", _capture_embeddings)

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
    assert saved_chunk_contents == [paragraph_1, paragraph_2, paragraph_3]
    assert embedding_calls == [saved_chunk_contents]
