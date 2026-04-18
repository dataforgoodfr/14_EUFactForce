"""
Pipeline steps: fetch (simulated API), save to S3 + Postgres, parse CSV and save elements.
This file is mostly a placeholder for future implementation.
Create a dedicated file for real pipeline steps.
"""

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id
from eu_fact_force.ingestion.embedding import add_embeddings
from eu_fact_force.ingestion.parsing import parse_file

from .models import Author, Document, DocumentChunk, SourceFile


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
    pdf_dir = Path(__file__).parents[2] / "data" / "data_collection" / "pdf"
    metadata = fetch_all(doi)

    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = None
    for parser in PARSERS:
        try:
            if parser.download_pdf(doi, pdf_dir):
                pdf_path = Path(pdf_dir) / f"{doi_to_id(doi)}.pdf"
                break
        except Exception as e:
            logging.warning(f"{parser.__class__.__name__} PDF error: {e}")

    return pdf_path, metadata


def save_to_s3_and_postgres(
    local_file_path: str | Path,
    metadata: dict[str, Any] | None = None,
    doi: str | None = None,
) -> SourceFile:
    """
    Read the local file at local_file_path (e.g. PDF, CSV, JPEG), upload it to S3
    (or default storage), and create a SourceFile in Postgres.
    """
    source_file = SourceFile.create_from_file(file_path=local_file_path, doi=doi)
    meta = metadata or {}
    keywords = meta.get("keywords", [])
    document, _ = Document.objects.update_or_create(
        source_file=source_file,
        defaults={
            "title": meta.get("title", ""),
            "doi": doi or "",
            "keywords": keywords if isinstance(keywords, list) else [],
        },
    )

    document.authors.set(Author.from_list(meta.get("authors", [])))

    return document


def save_chunks(document: Document, chunks: list[str]) -> list[DocumentChunk]:
    """
    Save the file chunks as DocumentChunks with a link to the source file.
    As a v0 we assume the chunks are the tags.
    """
    chunks = [
        DocumentChunk(document=document, content=tag, order=order)
        for order, tag in enumerate(chunks, start=1)
    ]
    DocumentChunk.objects.bulk_create(chunks)
    return chunks


def save_uploaded_file_to_document(document: Document, uploaded_file) -> None:
    """
    Save an uploaded file to a temp path, upload it to S3 and link the resulting
    SourceFile to the document. Raises ValueError if the document already has a source file.
    """
    if document.source_file_id is not None:
        raise ValueError("Document already has a PDF attached.")

    suffix = Path(uploaded_file.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        source_file = SourceFile.create_from_file(file_path=tmp_path, doi=document.doi or None)
        document.source_file = source_file
        document.save(update_fields=["source_file"])
    finally:
        tmp_path.unlink(missing_ok=True)


def parse_and_embed_document(document: Document) -> list[DocumentChunk]:
    """Parse an already-stored document's source file and embed the resulting chunks."""
    parts = parse_file(document)
    chunks = save_chunks(document, parts)
    add_embeddings(chunks)
    return chunks


def attach_pdf_to_document(document: Document, uploaded_file) -> list[DocumentChunk]:
    """
    Upload the provided PDF file to S3, link it to the document, then parse and embed.
    Raises ValueError if the document already has a source file.
    """
    save_uploaded_file_to_document(document, uploaded_file)
    return parse_and_embed_document(document)


def run_pipeline(doi: str) -> tuple[SourceFile, list[DocumentChunk]]:
    """
    Run the full pipeline: fetch -> save S3 + Postgres -> parse and save elements.
    Returns (source_file, list of DocumentChunk).
    """
    local_file_path, tags_pubmed = fetch_file_and_metadata(doi)
    document = save_to_s3_and_postgres(local_file_path, tags_pubmed, doi=doi)
    chunks = parse_and_embed_document(document)
    return document, chunks
