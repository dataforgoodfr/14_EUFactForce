"""
Seed the database from a curated CSV of articles.

Each row in the CSV must have at minimum a `doi` column. An optional `pdf_url`
column is used as the first attempt for PDF download before falling back to the
parser chain (Crossref, OpenAlex, PubMed, HAL, arXiv).

Rows without a `doi` are skipped and reported.

Usage:

  python -m eu_fact_force.ingestion.data_collection.seed_db \\
      --csv vaccine_autism_evidence_curated.csv

  # Dry-run: print what would be ingested without touching the DB
  python -m eu_fact_force.ingestion.data_collection.seed_db \\
      --csv vaccine_autism_evidence_curated.csv --dry-run
"""

import argparse
import csv
import logging
import os
import sys
import tempfile
from pathlib import Path

import requests

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

logger = logging.getLogger(__name__)

_PDF_TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Django setup (must run before any model import)
# ---------------------------------------------------------------------------

def _setup_django() -> None:
    from django.conf import settings
    if not settings.configured:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eu_fact_force.app.settings")
        import django
        django.setup()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

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
        # TODO: populate provider IDs (pmid, openalex_id, etc.) once parsers
        # expose their internal identifiers in the metadata dict.
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
                resp = requests.get(pdf_url, timeout=_PDF_TIMEOUT, headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                })
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_from_csv(args: argparse.Namespace) -> None:
    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if "doi" not in rows[0]:
        print("Error: CSV must have a 'doi' column.", file=sys.stderr)
        sys.exit(1)

    entries, skipped = [], []
    for row in rows:
        doi = row.get("doi", "").strip()
        article_id = row.get("article_id", "?")
        if not doi:
            skipped.append(article_id)
            logger.warning("seed.skip article_id=%s reason=no_doi", article_id)
            continue
        entries.append({
            "doi": doi,
            "pdf_url": row.get("pdf_url", "").strip() or None,
        })

    print(f"Loaded {len(entries)} articles from {args.csv}")
    if skipped:
        print(f"Skipped {len(skipped)} rows without DOI: {', '.join(skipped)}")

    if args.dry_run:
        print("\nDry run — no changes made. Articles that would be ingested:")
        for e in entries:
            pdf = e["pdf_url"] or "parser chain"
            print(f"  {e['doi']}  (pdf: {pdf})")
        return

    _setup_django()
    summary = bulk_ingest(entries)
    _print_summary(summary)


def _print_summary(summary: dict) -> None:
    print(f"\nIngestion complete:")
    print(f"  Ingested : {summary['ingested']}/{summary['total']}")
    print(f"  Failed   : {summary['failed']}/{summary['total']}")

    failed = [r for r in summary["results"] if not r.get("success")]
    if failed:
        print(f"\nFailed:")
        for r in failed:
            reason = r.get("reason") or r.get("error") or "unknown"
            print(f"  {r['doi']}: {reason}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed the database from a curated CSV of articles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv", required=True,
        help="Path to a curated CSV with at least a 'doi' column (e.g. vaccine_autism_evidence_curated.csv)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be ingested without writing to the database",
    )
    parser.set_defaults(func=cmd_from_csv)
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
