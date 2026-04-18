"""Tests for the production Docling parsing module."""

from pathlib import Path

import pytest

from eu_fact_force.ingestion.parsing.docling_parser import parse_file

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "jhab032.pdf"


@pytest.mark.skipif(
    not FIXTURE_PDF.exists(),
    reason="Fixture PDF not present",
)
def test_parse_file_returns_non_empty_fields():
    result = parse_file(FIXTURE_PDF)

    assert result["postprocessed_text"], "postprocessed_text must be non-empty"
    assert result["docling_output"], "docling_output must be a non-empty dict"
    assert result["parser_config"], "parser_config must be a non-empty dict"
    assert result["chunks"], "chunks must be non-empty"


@pytest.mark.skipif(
    not FIXTURE_PDF.exists(),
    reason="Fixture PDF not present",
)
def test_parse_file_docling_output_is_dict():
    result = parse_file(FIXTURE_PDF)

    assert isinstance(result["docling_output"], dict)


@pytest.mark.skipif(
    not FIXTURE_PDF.exists(),
    reason="Fixture PDF not present",
)
def test_parse_file_parser_config_has_version():
    result = parse_file(FIXTURE_PDF)

    config = result["parser_config"]
    assert "docling_version" in config
    assert isinstance(config["docling_version"], str)
    assert config["docling_version"]


@pytest.mark.skipif(
    not FIXTURE_PDF.exists(),
    reason="Fixture PDF not present",
)
def test_parse_file_chunks_are_strings():
    result = parse_file(FIXTURE_PDF)

    chunks = result["chunks"]
    assert len(chunks) >= 1
    assert all(isinstance(c, str) and c for c in chunks)
