"""
Ingestion pipeline services.
"""

import hashlib
import logging
import os
from pathlib import Path

import requests

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id
from eu_fact_force.ingestion.embedding import add_embeddings
from eu_fact_force.ingestion.models import Author, Document, DocumentChunk, IngestionRun, ParsedArtifact, SourceFile
from eu_fact_force.ingestion.parsing import parse_source_file

PIPELINE_VERSION = "0.1.0"


class DuplicateDOIError(Exception):
    pass


def hash_doi(doi: str) -> str:
    return hashlib.sha256(doi.encode()).hexdigest()


def ingest_by_doi(doi: str, pdf_url: str | None = None) -> IngestionRun:
    """
    Single canonical pipeline entry point for DOI-based ingestion.

    Creates IngestionRun and Document, fetches metadata, optionally downloads
    and parses a PDF, creates ParsedArtifact and DocumentChunks with embeddings.

    Raises DuplicateDOIError if the DOI already exists (no records created).
    Re-raises any other exception after recording the failure on IngestionRun.
    """
    if Document.objects.filter(doi=doi).exists():
        raise DuplicateDOIError(f"DOI '{doi}' is already ingested.")

    document = Document.objects.create(doi=doi, title="")
    run = IngestionRun.start(
        document=document,
        input_type=IngestionRun.InputType.DOI,
        input_identifier=doi,
        pipeline_version=PIPELINE_VERSION,
    )

    try:
        metadata = _acquire_metadata(doi, document, run)
        source_file = _store_source_file(doi, pdf_url, document, run)

        if source_file is None:
            run.status = IngestionRun.Status.SUCCESS
            run.success_kind = IngestionRun.SuccessKind.METADATA_ONLY
            run.stage = IngestionRun.Stage.DONE
            run.save(update_fields=["status", "success_kind", "stage"])
            return run

        parse_result = _parse_artifact(document, source_file, metadata, run)
        _chunk_and_embed(document, parse_result["chunks"], run)

        run.status = IngestionRun.Status.SUCCESS
        run.success_kind = IngestionRun.SuccessKind.FULL
        run.stage = IngestionRun.Stage.DONE
        run.save(update_fields=["status", "success_kind", "stage"])
        return run

    except Exception as exc:
        run.status = IngestionRun.Status.FAILED
        run.error_stage = run.stage
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_stage", "error_message"])
        raise


def _acquire_metadata(doi: str, document: Document, run: IngestionRun) -> dict:
    metadata = fetch_all(doi)
    keywords = metadata.get("keywords", [])
    document.title = metadata.get("title") or ""
    document.keywords = keywords if isinstance(keywords, list) else []
    document.save(update_fields=["title", "keywords"])
    document.authors.set(Author.from_list(metadata.get("authors", [])))
    run.raw_provider_payload = metadata
    run.save(update_fields=["raw_provider_payload"])
    return metadata


def _store_source_file(
    doi: str, pdf_url: str | None, document: Document, run: IngestionRun
) -> SourceFile | None:
    pdf_path = _download_pdf(doi, pdf_url)
    if pdf_path is None:
        return None

    run.stage = IngestionRun.Stage.STORE
    run.save(update_fields=["stage"])

    source_file = SourceFile.create_from_file(file_path=pdf_path, doi=doi)
    document.source_file = source_file
    document.save(update_fields=["source_file"])
    run.source_file = source_file
    run.save(update_fields=["source_file"])
    return source_file


def _parse_artifact(
    document: Document, source_file: SourceFile, metadata: dict, run: IngestionRun
) -> dict:
    run.stage = IngestionRun.Stage.PARSE
    run.save(update_fields=["stage"])

    parse_result = parse_source_file(source_file)
    ParsedArtifact.objects.create(
        document=document,
        docling_output=parse_result["docling_output"],
        postprocessed_text=parse_result["postprocessed_text"],
        metadata_extracted=metadata,
        parser_config=parse_result["parser_config"],
    )
    return parse_result


def _chunk_and_embed(document: Document, chunks: list[str], run: IngestionRun) -> None:
    run.stage = IngestionRun.Stage.CHUNK
    run.save(update_fields=["stage"])

    chunk_objs = [
        DocumentChunk(document=document, content=chunk, order=order)
        for order, chunk in enumerate(chunks, start=1)
    ]
    DocumentChunk.objects.bulk_create(chunk_objs)
    chunk_objs = list(DocumentChunk.objects.filter(document=document).order_by("order"))
    add_embeddings(chunk_objs)


def _download_pdf(doi: str, pdf_url: str | None) -> Path | None:
    """Download PDF from a direct URL or by trying each parser. Returns local path or None."""
    pdf_dir = Path(__file__).parents[2] / "data" / "data_collection" / "pdf"
    os.makedirs(pdf_dir, exist_ok=True)
    output_path = pdf_dir / f"{doi_to_id(doi)}.pdf"

    if pdf_url:
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            if response.content.startswith(b"%PDF"):
                with open(output_path, "wb") as fh:
                    fh.write(response.content)
                return output_path
        except Exception as exc:
            logging.warning("Failed to download PDF from %s: %s", pdf_url, exc)
        return None

    for parser in PARSERS:
        try:
            if parser.download_pdf(doi, pdf_dir):
                return output_path
        except Exception as exc:
            logging.warning("%s PDF error: %s", parser.__class__.__name__, exc)
    return None
