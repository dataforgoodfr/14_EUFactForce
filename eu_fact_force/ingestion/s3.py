from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def save_file_to_s3(file_path: Path) -> str:
    """
    Upload the file to S3 (or default storage).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Local file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    file_content = file_path.read_bytes()
    s3_key = f"ingestion/sources/{file_path.name}"
    default_storage.save(s3_key, ContentFile(file_content))
    return s3_key
