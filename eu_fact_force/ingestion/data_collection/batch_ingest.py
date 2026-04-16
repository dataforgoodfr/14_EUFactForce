"""
Batch-ingest articles by DOI into the database.

For each entry:
  1. Fetch merged metadata via all configured parsers (fetch_all)
  2. Attempt to download a PDF — tries a direct url first (if provided),
     then falls back to the parser chain
  3. Create a Document record linked to the SourceFile (skips if DOI already exists)

The Document → SourceFile relationship is a OneToOne with Document holding the FK,
so SourceFile must be created before Document.

Requires Django to be set up before calling any public function here.
"""

import logging
import tempfile
from pathlib import Path

import requests

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

logger = logging.getLogger(__name__)

_PDF_TIMEOUT = 60  # seconds


def ingest_article(doi: str, pdf_url: str | None = None) -> dict:
    """
    Ingest a single article by DOI.

    pdf_url: if provided, tried before the parser chain for PDF download.

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
    source_file = _download_and_store_pdf(doi, SourceFile, pdf_url=pdf_url)

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


def bulk_ingest(entries: list[dict]) -> dict:
    """
    Ingest a list of articles. Each entry is a dict with keys:
      doi (str, required), pdf_url (str, optional)

    Returns a summary dict with counts and per-article results.
    """
    ingested, failed = [], []
    for i, entry in enumerate(entries, 1):
        doi = entry["doi"]
        pdf_url = entry.get("pdf_url")
        logger.info("ingest.progress n=%d total=%d doi=%s", i, len(entries), doi)
        result = ingest_article(doi, pdf_url=pdf_url)
        (ingested if result["success"] else failed).append(result)

    return {
        "total": len(entries),
        "ingested": len(ingested),
        "failed": len(failed),
        "results": ingested + failed,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_and_store_pdf(doi: str, SourceFile, pdf_url: str | None = None) -> object:
    """
    Download a PDF and upload to storage. Tries pdf_url directly first (if given),
    then falls back to the parser chain.
    Returns the created SourceFile instance, or None if no PDF was found.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        expected_path = Path(tmpdir) / f"{doi_to_id(doi)}.pdf"

        # 1. Try the known URL from the curated source
        if pdf_url:
            try:
                resp = requests.get(pdf_url, timeout=_PDF_TIMEOUT)
                resp.raise_for_status()
                if resp.content.startswith(b"%PDF"):
                    expected_path.write_bytes(resp.content)
                    source_file = SourceFile.create_from_file(expected_path, doi=doi)
                    logger.info("ingest.pdf_stored doi=%s via=direct_url", doi)
                    return source_file
                logger.warning("ingest.direct_url_not_pdf doi=%s url=%s", doi, pdf_url)
            except Exception as e:
                logger.warning("ingest.direct_url_failed doi=%s url=%s error=%s", doi, pdf_url, e)

        # 2. Fall back to parser chain
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
                logger.info("ingest.pdf_stored doi=%s via=%s", doi, parser.__class__.__name__)
                return source_file
            except Exception as e:
                logger.warning("ingest.pdf_upload_failed doi=%s error=%s", doi, e)
                return None

    logger.warning("ingest.no_pdf doi=%s", doi)
    return None
