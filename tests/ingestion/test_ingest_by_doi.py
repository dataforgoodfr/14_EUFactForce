"""Tests for ingest_by_doi: full path, metadata-only, duplicate DOI, failure."""

from pathlib import Path
from unittest.mock import patch

import pytest

from eu_fact_force.ingestion.models import (
    Document,
    DocumentChunk,
    IngestionRun,
    ParsedArtifact,
    SourceFile,
)
from eu_fact_force.ingestion.services import (
    PIPELINE_VERSION,
    DuplicateDOIError,
    ingest_by_doi,
)

_FAKE_METADATA = {
    "found": True,
    "title": "Vaccine Efficacy Study",
    "authors": [{"name": "Alice Smith", "orcid": None}],
    "keywords": ["vaccines", "efficacy"],
}

_FAKE_PARSE_RESULT = {
    "docling_output": {"pages": 2, "tables": []},
    "postprocessed_text": "Vaccines are effective.",
    "parser_config": {"docling_version": "2.0", "ocr": False},
    "chunks": ["Vaccines are effective.", "Further research needed."],
}


def _fake_save_file_to_s3(file_path):
    return f"ingestion/sources/{Path(file_path).name}"


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=Path("/tmp/fake.pdf"))
@patch("eu_fact_force.ingestion.models.save_file_to_s3", side_effect=_fake_save_file_to_s3)
@patch("eu_fact_force.ingestion.services.parse_source_file", return_value=_FAKE_PARSE_RESULT)
@patch("eu_fact_force.ingestion.services.add_embeddings")
def test_full_path(mock_embed, mock_parse, mock_s3, mock_download, mock_fetch):
    doi = "10.1234/full-path"
    run = ingest_by_doi(doi)

    assert run.status == IngestionRun.Status.SUCCESS
    assert run.success_kind == IngestionRun.SuccessKind.FULL
    assert run.stage == IngestionRun.Stage.DONE
    assert run.pipeline_version == PIPELINE_VERSION
    assert run.raw_provider_payload == _FAKE_METADATA

    doc = run.document
    assert doc.doi == doi
    assert doc.title == "Vaccine Efficacy Study"
    assert doc.keywords == ["vaccines", "efficacy"]
    assert doc.source_file is not None

    assert run.source_file is not None
    assert run.source_file == doc.source_file

    artifact = ParsedArtifact.objects.get(document=doc)
    assert artifact.docling_output == _FAKE_PARSE_RESULT["docling_output"]
    assert artifact.postprocessed_text == _FAKE_PARSE_RESULT["postprocessed_text"]
    assert artifact.parser_config == _FAKE_PARSE_RESULT["parser_config"]
    assert artifact.metadata_extracted == _FAKE_METADATA

    chunks = list(DocumentChunk.objects.filter(document=doc).order_by("order"))
    assert len(chunks) == 2
    assert chunks[0].content == "Vaccines are effective."
    assert chunks[1].content == "Further research needed."

    mock_embed.assert_called_once()


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=None)
def test_metadata_only_path(mock_download, mock_fetch):
    doi = "10.1234/metadata-only"
    run = ingest_by_doi(doi)

    assert run.status == IngestionRun.Status.SUCCESS
    assert run.success_kind == IngestionRun.SuccessKind.METADATA_ONLY
    assert run.stage == IngestionRun.Stage.DONE
    assert run.pipeline_version == PIPELINE_VERSION
    assert run.raw_provider_payload == _FAKE_METADATA

    doc = run.document
    assert doc.doi == doi
    assert doc.title == "Vaccine Efficacy Study"
    assert doc.source_file is None
    assert run.source_file is None

    assert not SourceFile.objects.filter(doi=doi).exists()
    assert not ParsedArtifact.objects.filter(document=doc).exists()
    assert not DocumentChunk.objects.filter(document=doc).exists()


@pytest.mark.django_db
def test_duplicate_doi_returns_early():
    doi = "10.1234/duplicate"
    source_file = SourceFile.objects.create(doi=doi, s3_key="key", status=SourceFile.Status.STORED)
    Document.objects.create(title="Existing Paper", doi=doi, source_file=source_file)

    doc_count_before = Document.objects.count()
    run_count_before = IngestionRun.objects.count()

    with pytest.raises(DuplicateDOIError, match=doi):
        ingest_by_doi(doi)

    assert Document.objects.count() == doc_count_before
    assert IngestionRun.objects.count() == run_count_before


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", side_effect=RuntimeError("API timeout"))
def test_failure_mid_pipeline_records_error(mock_fetch):
    doi = "10.1234/fail-test"

    with pytest.raises(RuntimeError, match="API timeout"):
        ingest_by_doi(doi)

    run = IngestionRun.objects.get(document__doi=doi)
    assert run.status == IngestionRun.Status.FAILED
    assert run.error_stage == IngestionRun.Stage.ACQUIRE
    assert "API timeout" in run.error_message

    # Document was created and left in place
    assert Document.objects.filter(doi=doi).exists()
