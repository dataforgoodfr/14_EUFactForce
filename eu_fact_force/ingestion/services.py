"""
Pipeline steps: fetch (simulated API), save to S3 + Postgres, parse CSV and save elements.
This file is mostly a placeholder for future implementation.
Create a dedicated file for real pipeline steps.
"""

import hashlib
import logging
import os
from pathlib import Path

from eu_fact_force.ingestion.embedding import add_embeddings
from eu_fact_force.ingestion.parsing import parse_file

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

from .models import DocumentChunk, FileMetadata, SourceFile


def hash_doi(doi: str) -> str:
    """
    Hash the DOI to a string of 128 bits.
    """
    return hashlib.sha256(doi.encode()).hexdigest()


def fetch_file_and_metadata(doi: str) -> tuple[Path | None, dict]:
    """
    Simulate an API call to fetch a PDF and metadata.
    V0: returns a local file path and a list of tags (tags_pubmed); no real HTTP call.
    The returned path must point to an existing local file (e.g. PDF, CSV, JPEG).
    """
    pdf_dir = os.path.join(os.path.dirname(__file__), "data_collection", "pdf")
    metadata = fetch_all(doi)

    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = None
    for parser in PARSERS:
        try:
            if parser.download_pdf(doi, pdf_dir):
                pdf_path = Path(pdf_dir) / f"{doi_to_id(doi)}_{parser.api_name}.pdf"
                break
        except Exception as e:
            logging.warning(f"{parser.__class__.__name__} PDF error: {e}")

    return pdf_path, metadata


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
    document_parts = parse_file(source_file)
    chunks = save_chunks(source_file, document_parts)
    add_embeddings(chunks)
    return source_file, chunks
