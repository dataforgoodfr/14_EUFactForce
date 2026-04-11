import io
import os
from pathlib import Path

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Alignés sur docker-compose (RustFS) pour dev local et tests.
AWS_ACCESS_KEY_ID_DEFAULT = "minioadmin"
AWS_SECRET_ACCESS_KEY_DEFAULT = "minioadmin"
AWS_STORAGE_BUCKET_NAME_DEFAULT = "eu-fact-force-files"


def get_default_bucket() -> str | None:
    """Return the default S3 bucket name when S3 is configured, else None."""
    return (
        os.environ.get("AWS_STORAGE_BUCKET_NAME", AWS_STORAGE_BUCKET_NAME_DEFAULT)
        or None
    )


def _is_local_endpoint(endpoint_url: str | None) -> bool:
    """True if endpoint points to local S3 (RustFS, MinIO, LocalStack)."""
    if not endpoint_url:
        return False
    return "localhost" in endpoint_url or "127.0.0.1" in endpoint_url


def get_s3_client():
    """
    Build boto3 S3 client using project config (endpoint, credentials, region).
    Single entry point for all S3 access; same config as default_storage (django-storages).
    Lit endpoint et credentials dans os.environ au moment de l'appel pour que les tests
    (conftest) puissent forcer RustFS local même si settings ont été chargés avant.
    Si l'endpoint est local (localhost / 127.0.0.1), on force minioadmin pour RustFS.
    """
    endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL") or getattr(
        settings, "AWS_S3_ENDPOINT_URL", None
    )
    endpoint_url = endpoint_url or None
    if _is_local_endpoint(endpoint_url):
        access_key = AWS_ACCESS_KEY_ID_DEFAULT
        secret_key = AWS_SECRET_ACCESS_KEY_DEFAULT
    else:
        access_key = os.environ.get("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID_DEFAULT)
        secret_key = os.environ.get(
            "AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY_DEFAULT
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_S3_REGION_NAME", "eu-west-1"),
    )


def save_file_to_s3(file_path: Path) -> str:
    """
    Upload the file to S3 via get_s3_client(). Raises ImproperlyConfigured if no bucket is configured.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Local file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    bucket = get_default_bucket()
    if not bucket:
        raise ImproperlyConfigured(
            "AWS_STORAGE_BUCKET_NAME must be set to upload files to S3."
        )

    file_content = file_path.read_bytes()
    s3_key = f"ingestion/sources/{file_path.name}"
    client = get_s3_client()
    client.upload_fileobj(io.BytesIO(file_content), bucket, s3_key)
    return s3_key
