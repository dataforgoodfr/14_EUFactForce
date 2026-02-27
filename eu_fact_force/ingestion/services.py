"""
Pipeline steps: fetch (simulated API), save to S3 + Postgres, parse CSV and save elements.
This file is mostly a placeholder for future implementation.
Create a dedicated file for real pipeline steps.
"""

from pathlib import Path

from .models import DocumentChunk, FileMetadata, SourceFile


def fetch_file_and_metadata(doi: str) -> tuple[str, list[str]]:
    """
    Simulate an API call to fetch a PDF and metadata.
    V0: returns a local file path and a list of tags (tags_pubmed); no real HTTP call.
    The returned path must point to an existing local file (e.g. PDF, CSV, JPEG).
    """
    # V0: fixed path; replace with a real local path or path from API response
    filename = Path(__file__).parents[2] / doi
    tags_pubmed = ["simulated", doi]
    return filename, tags_pubmed


def save_to_s3_and_postgres(
    local_file_path: str | Path,
    tags_pubmed: list[str] | None = None,
    doi: str | None = None,
) -> SourceFile:
    """
    Read the local file at local_file_path (e.g. PDF, CSV, JPEG), upload it to S3
    (or default storage), and create SourceFile + FileMetadata in Postgres.
    """
    source_file = SourceFile.create_from_file(file_path=local_file_path, doi=doi)
    FileMetadata.objects.create(source_file=source_file, tags_pubmed=tags_pubmed)
    return source_file


def parse_file(source_file: SourceFile) -> list[str]:
    """
    Parse the file and return a list of chunks.
    As a v0 we assume the chunks are the tags.
    """
    return source_file.metadata.tags_pubmed


def save_chunks(source_file: SourceFile, chunks: list[str]) -> list[DocumentChunk]:
    """
    Save the file chunks as DocumentChunks with a link to the source file.
    As a v0 we assume the chunks are the tags.
    """
    chunks = [
        DocumentChunk(source_file=source_file, content=tag, order=order)
        for order, tag in enumerate(chunks, start=1)
    ]
    DocumentChunk.objects.bulk_create(chunks)

    source_file.status = SourceFile.Status.PARSED
    source_file.save(update_fields=["status", "updated_at"])
    return chunks


def run_pipeline(doi: str) -> tuple[SourceFile, list[DocumentChunk]]:
    """
    Run the full pipeline: fetch -> save S3 + Postgres -> parse and save elements.
    Returns (source_file, list of DocumentChunk).
    """
    local_file_path, tags_pubmed = fetch_file_and_metadata(doi)
    source_file = save_to_s3_and_postgres(local_file_path, tags_pubmed, doi=doi)
    chunks = parse_file(source_file)
    save_chunks(source_file, chunks)
    return source_file, chunks
