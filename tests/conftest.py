"""Pytest configuration and fixtures."""
import os
import sys
from pathlib import Path

import pytest
from django.test import override_settings

# Ensure project root is on path so Django settings and eu_fact_force are found
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Forcer S3 sur MinIO local (docker compose) pour toute la session de tests :
# endpoint localhost:9000 et credentials minioadmin. Évite InvalidAccessKeyId
# si .env contient d’autres clés ou si un test appelle vraiment S3.
os.environ["AWS_S3_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["AWS_STORAGE_BUCKET_NAME"] = "eu-fact-force-files"


@pytest.fixture(scope="session", autouse=True)
def ensure_minio_bucket():
    """
    Crée le bucket S3 sur MinIO local s'il n'existe pas (évite NoSuchBucket en tests).
    Uniquement lorsque l'endpoint pointe vers localhost (MinIO), pas en production.
    """
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL", "") or ""
    if "localhost" not in endpoint and "127.0.0.1" not in endpoint:
        return
    try:
        from botocore.exceptions import ClientError

        from eu_fact_force.ingestion.s3 import get_default_bucket, get_s3_client

        bucket = get_default_bucket()
        if not bucket:
            return
        client = get_s3_client()
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchBucket", "404"):
                client.create_bucket(Bucket=bucket)
            else:
                raise
        except Exception:
            pass
    except Exception:
        pass  # MinIO non démarré ou autre erreur, on ignore


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
