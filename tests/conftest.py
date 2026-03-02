"""Pytest configuration and fixtures."""
import sys
from pathlib import Path

import pytest
from django.test import override_settings

# Ensure project root is on path so Django settings and eu_fact_force are found
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_storage(tmp_path):
    """
    Override default storage with a temporary directory (simulated S3).
    All files saved during the test go to this dir; pytest cleans it up after the test.
    """
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    with override_settings(
        STORAGES={
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(storage_dir)},
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    ):
        yield storage_dir
