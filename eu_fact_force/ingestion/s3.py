import io
import os
from pathlib import Path

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Alignés sur docker-compose (MinIO) pour dev local et tests.
AWS_STORAGE_BUCKET_NAME_DEFAULT = "eu-fact-force-files"


def get_default_bucket() -> str | None:
    """Return the default S3 bucket name when S3 is configured, else None."""
    return (
        os.environ.get("AWS_STORAGE_BUCKET_NAME", AWS_STORAGE_BUCKET_NAME_DEFAULT)
        or None
    )


def get_s3_client():
    """
    Build boto3 S3 client using project config (endpoint, credentials, region).
    Single entry point for all S3 access; same config as default_storage (django-storages).
    Lit endpoint et credentials dans os.environ au moment de l'appel pour que les tests
    (conftest) puissent forcer MinIO local même si settings ont été chargés avant.
    """
    endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL") or getattr(
        settings, "AWS_S3_ENDPOINT_URL", None
    )
    endpoint_url = endpoint_url or None

    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise ImproperlyConfigured(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set."
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_S3_REGION_NAME", "eu-west-1"),
        config=Config(
            retries={"max_attempts": 5, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60,
            signature_version=os.environ.get("AWS_S3_SIGNATURE_VERSION", "s3v4"),
            s3={"addressing_style": os.environ.get("AWS_S3_ADDRESSING_STYLE", "path")},
        ),
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
