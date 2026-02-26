"""Tests for SourceFile model (e.g. storage cleanup on delete)."""

from pathlib import Path

import pytest

from eu_fact_force.ingestion.models import SourceFile
from eu_fact_force.ingestion.services import run_pipeline

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
