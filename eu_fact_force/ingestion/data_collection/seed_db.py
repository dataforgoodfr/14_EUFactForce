"""
Seed the database with articles on a given topic.

Three modes:

  search   -- Query PubMed + Crossref and save results to JSON for inspection
  ingest   -- Ingest articles from a saved search JSON into the database
  full     -- search + ingest in one shot

Usage:

  # Search and inspect results before ingesting
  python -m eu_fact_force.ingestion.data_collection.seed_db search \\
      --query "vaccine autism" --output search_results.json --max-results 100

  # Ingest from a previous search
  python -m eu_fact_force.ingestion.data_collection.seed_db ingest \\
      --search-results search_results.json --max-articles 50

  # Full pipeline in one command
  python -m eu_fact_force.ingestion.data_collection.seed_db full \\
      --query "vaccine autism" --max-articles 50
"""

import argparse
import json
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
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> None:
    from eu_fact_force.ingestion.data_collection.search import ArticleSearcher

    searcher = ArticleSearcher()
    results = searcher.search(
        query=args.query,
        max_results=args.max_results,
        min_year=args.min_year,
    )

    output = {
        "query": args.query,
        "total": len(results),
        "results": [r.to_dict() for r in results],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    oa_count = sum(1 for r in results if r.open_access)
    print(f"Found {len(results)} articles ({oa_count} open access)")
    print(f"Saved to {args.output}")


def cmd_ingest(args: argparse.Namespace) -> None:
    _setup_django()
    from eu_fact_force.ingestion.data_collection.batch_ingest import bulk_ingest

    with open(args.search_results, encoding="utf-8") as f:
        data = json.load(f)

    dois = [r["doi"] for r in data.get("results", []) if r.get("doi")]
    print(f"Loaded {len(dois)} DOIs from {args.search_results}")

    summary = bulk_ingest(dois, max_articles=args.max_articles)
    _print_summary(summary)


def cmd_full(args: argparse.Namespace) -> None:
    from eu_fact_force.ingestion.data_collection.search import ArticleSearcher

    # --- Search ---
    print(f"Searching for: {args.query!r}")
    searcher = ArticleSearcher()
    results = searcher.search(
        query=args.query,
        max_results=args.max_results,
        min_year=args.min_year,
    )
    oa_count = sum(1 for r in results if r.open_access)
    print(f"Found {len(results)} articles ({oa_count} open access)")

    if not results:
        print("Nothing to ingest.")
        return

    # --- Ingest ---
    _setup_django()
    from eu_fact_force.ingestion.data_collection.batch_ingest import bulk_ingest

    dois = [r.doi for r in results]
    summary = bulk_ingest(dois, max_articles=args.max_articles)
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
        print(f"\nFailed DOIs:")
        for r in failed:
            reason = r.get("reason") or r.get("error") or "unknown"
            print(f"  {r['doi']}: {reason}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed the database with articles on a topic.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # search
    p = sub.add_parser("search", help="Search PubMed + Crossref and save results")
    p.add_argument("--query", required=True)
    p.add_argument("--output", default="search_results.json",
                   help="Path to write results JSON (default: search_results.json)")
    p.add_argument("--max-results", type=int, default=100,
                   help="Max results per source (default: 100)")
    p.add_argument("--min-year", type=int, default=None)
    p.set_defaults(func=cmd_search)

    # ingest
    p = sub.add_parser("ingest", help="Ingest articles from a search results JSON")
    p.add_argument("--search-results", required=True,
                   help="Path to search_results.json from a previous 'search' run")
    p.add_argument("--max-articles", type=int, default=None)
    p.set_defaults(func=cmd_ingest)

    # full
    p = sub.add_parser("full", help="Search + ingest in one shot")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=100)
    p.add_argument("--max-articles", type=int, default=None)
    p.add_argument("--min-year", type=int, default=None)
    p.set_defaults(func=cmd_full)

    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
