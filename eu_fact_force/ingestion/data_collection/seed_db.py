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

logger = logging.getLogger(__name__)


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
# Command
# ---------------------------------------------------------------------------

def cmd_from_csv(args: argparse.Namespace) -> None:
    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if "doi" not in rows[0]:
        print(f"Error: CSV must have a 'doi' column.", file=sys.stderr)
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
    from eu_fact_force.ingestion.data_collection.batch_ingest import bulk_ingest

    summary = bulk_ingest(entries)
    _print_summary(summary)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
