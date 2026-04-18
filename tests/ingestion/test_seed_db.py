"""Tests for the seed_db management command."""

import csv
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from eu_fact_force.ingestion.models import Document, IngestionRun

_FAKE_METADATA = {
    "found": True,
    "title": "Test Paper",
    "authors": [],
    "keywords": [],
}

_FAKE_PARSE_RESULT = {
    "docling_output": {},
    "postprocessed_text": "text",
    "parser_config": {},
    "chunks": ["chunk one"],
}


def _write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = rows[0].keys() if rows else ["doi"]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=None)
def test_seed_db_creates_ingestion_runs(mock_download, mock_fetch, tmp_path):
    csv_file = tmp_path / "dois.csv"
    _write_csv(
        [
            {"doi": "10.1234/paper-a"},
            {"doi": "10.1234/paper-b"},
        ],
        csv_file,
    )

    call_command("seed_db", csv=str(csv_file))

    assert IngestionRun.objects.count() == 2
    assert Document.objects.filter(doi="10.1234/paper-a").exists()
    assert Document.objects.filter(doi="10.1234/paper-b").exists()


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=None)
def test_seed_db_skips_rows_without_doi(mock_download, mock_fetch, tmp_path):
    csv_file = tmp_path / "dois.csv"
    _write_csv(
        [
            {"doi": "10.1234/valid"},
            {"doi": ""},
            {"doi": "10.1234/also-valid"},
        ],
        csv_file,
    )

    stderr = StringIO()
    call_command("seed_db", csv=str(csv_file), stderr=stderr)

    assert IngestionRun.objects.count() == 2
    assert "missing doi" in stderr.getvalue()


@pytest.mark.django_db
def test_seed_db_dry_run_does_not_write(tmp_path):
    csv_file = tmp_path / "dois.csv"
    _write_csv([{"doi": "10.1234/dry-run-paper"}], csv_file)

    stdout = StringIO()
    call_command("seed_db", csv=str(csv_file), dry_run=True, stdout=stdout)

    assert IngestionRun.objects.count() == 0
    assert Document.objects.count() == 0
    assert "10.1234/dry-run-paper" in stdout.getvalue()


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=None)
def test_seed_db_skips_duplicate_in_csv(mock_download, mock_fetch, tmp_path):
    csv_file = tmp_path / "dois.csv"
    _write_csv(
        [
            {"doi": "10.1234/dup"},
            {"doi": "10.1234/dup"},
        ],
        csv_file,
    )

    call_command("seed_db", csv=str(csv_file))

    assert IngestionRun.objects.count() == 1


@pytest.mark.django_db
@patch("eu_fact_force.ingestion.services.fetch_all", return_value=_FAKE_METADATA)
@patch("eu_fact_force.ingestion.services._download_pdf", return_value=None)
def test_seed_db_skips_doi_already_in_db(mock_download, mock_fetch, tmp_path):
    Document.objects.create(doi="10.1234/existing", title="Pre-existing")

    csv_file = tmp_path / "dois.csv"
    _write_csv(
        [
            {"doi": "10.1234/existing"},
            {"doi": "10.1234/new"},
        ],
        csv_file,
    )

    stderr = StringIO()
    call_command("seed_db", csv=str(csv_file), stderr=stderr)

    assert IngestionRun.objects.count() == 1
    assert "Duplicate" in stderr.getvalue()


def test_seed_db_raises_on_missing_file(tmp_path):
    with pytest.raises(CommandError, match="File not found"):
        call_command("seed_db", csv=str(tmp_path / "nonexistent.csv"))


def test_seed_db_raises_on_missing_doi_column(tmp_path):
    csv_file = tmp_path / "no_doi.csv"
    _write_csv([{"title": "Paper Without DOI Column"}], csv_file)

    with pytest.raises(CommandError, match="doi"):
        call_command("seed_db", csv=str(csv_file))
