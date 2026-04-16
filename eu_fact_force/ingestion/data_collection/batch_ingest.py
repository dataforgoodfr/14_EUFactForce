"""
Batch-ingest articles by DOI into the database.

For each DOI:
  1. Fetch merged metadata via all configured parsers (fetch_all)
  2. Attempt to download a PDF and upload it to storage as a SourceFile
  3. Create a Document record linked to the SourceFile (skips if DOI already exists)

The Document → SourceFile relationship is a OneToOne with Document holding the FK,
so SourceFile must be created before Document.

Requires Django to be set up before calling any public function here.
"""

import logging
import tempfile
from pathlib import Path

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

logger = logging.getLogger(__name__)


def ingest_article(doi: str) -> dict:
    """
    Ingest a single article by DOI.

    Returns a result dict with keys:
      success (bool), doi (str), reason (str, on failure),
      document_id (int, on success), created (bool), has_pdf (bool)
    """
    # Lazy import: Django must be set up by the caller before this runs
    from eu_fact_force.ingestion.models import Document, SourceFile

    if Document.objects.filter(doi=doi).exists():
        logger.info("ingest.skip doi=%s reason=already_exists", doi)
        return {"success": False, "doi": doi, "reason": "already_exists"}

    logger.info("ingest.start doi=%s", doi)
    metadata = fetch_all(doi)
    if not metadata.get("found"):
        logger.warning("ingest.no_metadata doi=%s", doi)
        return {"success": False, "doi": doi, "reason": "no_metadata"}

    # SourceFile must exist before Document (Document holds the FK)
    source_file = _download_and_store_pdf(doi, SourceFile)

    document = Document.objects.create(
        doi=doi,
        title=metadata.get("article name") or "",
        external_ids={},
        source_file=source_file,  # None if no PDF found — that's fine
    )
    logger.info("ingest.document_created doi=%s id=%d has_pdf=%s",
                doi, document.pk, source_file is not None)

    return {
        "success": True,
        "doi": doi,
        "document_id": document.pk,
        "created": True,
        "has_pdf": source_file is not None,
    }


def bulk_ingest(dois: list[str], max_articles: int | None = None) -> dict:
    """
    Ingest a list of DOIs. Returns a summary dict with counts and per-article results.
    """
    if max_articles:
        dois = dois[:max_articles]

    ingested, failed = [], []
    for i, doi in enumerate(dois, 1):
        logger.info("ingest.progress n=%d total=%d doi=%s", i, len(dois), doi)
        result = ingest_article(doi)
        (ingested if result["success"] else failed).append(result)

    return {
        "total": len(dois),
        "ingested": len(ingested),
        "failed": len(failed),
        "results": ingested + failed,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_and_store_pdf(doi: str, SourceFile) -> object:
    """
    Download a PDF via the parser chain and upload to storage.
    Returns the created SourceFile instance, or None if no PDF was found.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        expected_path = Path(tmpdir) / f"{doi_to_id(doi)}.pdf"

        for parser in PARSERS:
            try:
                if not parser.download_pdf(doi, tmpdir):
                    continue
            except Exception as e:
                logger.debug("ingest.pdf_parser_failed parser=%s error=%s",
                             parser.__class__.__name__, e)
                continue

            if not expected_path.exists():
                continue

            try:
                source_file = SourceFile.create_from_file(expected_path, doi=doi)
                logger.info("ingest.pdf_stored doi=%s s3_key=%s", doi, source_file.s3_key)
                return source_file
            except Exception as e:
                logger.warning("ingest.pdf_upload_failed doi=%s error=%s", doi, e)
                return None

    logger.warning("ingest.no_pdf doi=%s", doi)
    return None
