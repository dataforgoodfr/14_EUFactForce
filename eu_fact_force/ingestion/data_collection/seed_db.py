"""
End-to-end seed database generation: search → filter → ingest articles.

This is the main entry point for building a seed database of articles
on a specific topic (e.g., vaccine-autism).

Usage:
    # Search for articles and save results
    python -m eu_fact_force.ingestion.data_collection.seed_db search \
        --query "vaccine autism" \
        --output-dir ./vaccine_autism_seed \
        --max-results 100

    # Ingest the search results into local files
    python -m eu_fact_force.ingestion.data_collection.seed_db ingest \
        --search-results ./vaccine_autism_seed/search_results.json \
        --output-dir ./vaccine_autism_seed \
        --max-articles 50

    # Full pipeline (search + ingest)
    python -m eu_fact_force.ingestion.data_collection.seed_db full \
        --query "vaccine autism" \
        --output-dir ./vaccine_autism_seed \
        --max-articles 50
"""

import argparse
import json
import logging
import os
from datetime import datetime

from eu_fact_force.ingestion.data_collection.search import search_and_save
from eu_fact_force.ingestion.data_collection.batch_ingest import (
    load_search_results,
    ingest_article,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_search(args):
    """Command: Search for articles on a topic."""
    os.makedirs(args.output_dir, exist_ok=True)

    search_results_file = os.path.join(args.output_dir, "search_results.json")
    logger.info(f"Searching for: {args.query}")
    logger.info(f"Output: {search_results_file}")

    results = search_and_save(
        query=args.query,
        output_json=search_results_file,
        max_results=args.max_results,
        min_year=args.min_year,
    )

    logger.info(f"\n✓ Found {results['summary']['total_unique']} unique articles")
    logger.info(f"  - {results['summary']['open_access_count']} open access")
    logger.info(f"  - {results['summary']['pubmed_count']} from PubMed")
    logger.info(f"  - {results['summary']['crossref_count']} from Crossref")


def cmd_ingest(args):
    """Command: Ingest articles from search results."""
    # Load search results
    results = load_search_results(args.search_results)
    logger.info(f"Loaded {len(results)} search results")

    if args.max_articles:
        results = results[: args.max_articles]

    # Setup directories
    json_dir = os.path.join(args.output_dir, "json")
    pdf_dir = os.path.join(args.output_dir, "pdf")

    logger.info(f"Ingesting {len(results)} articles...")
    logger.info(f"Output: {args.output_dir}")

    ingested = []
    failed = []

    for i, result in enumerate(results):
        doi = result["doi"]
        logger.info(f"[{i+1}/{len(results)}] {doi}")

        status = ingest_article(
            doi=doi,
            json_dir=json_dir,
            pdf_dir=pdf_dir,
            skip_pdf=args.skip_pdf,
        )
        if status["success"]:
            ingested.append(status)
        else:
            failed.append(status)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"Successful: {len(ingested)}/{len(results)}")
    logger.info(f"Failed: {len(failed)}/{len(results)}")

    if failed and len(failed) <= 10:
        logger.warning("\nFailed:")
        for f in failed:
            logger.warning(f"  - {f['doi']}: {f.get('error', f.get('reason', '?'))}")


def cmd_full(args):
    """Command: Full pipeline (search + ingest)."""
    os.makedirs(args.output_dir, exist_ok=True)

    # Step 1: Search
    logger.info("=" * 60)
    logger.info("STEP 1: Searching for articles...")
    logger.info("=" * 60)

    search_results_file = os.path.join(args.output_dir, "search_results.json")
    results = search_and_save(
        query=args.query,
        output_json=search_results_file,
        max_results=args.max_results,
        min_year=args.min_year,
    )

    logger.info(f"\n✓ Found {results['summary']['total_unique']} unique articles")
    logger.info(f"  - {results['summary']['open_access_count']} open access")

    # Step 2: Ingest
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Ingesting articles...")
    logger.info("=" * 60)

    search_results = load_search_results(search_results_file)
    if args.max_articles:
        search_results = search_results[: args.max_articles]

    json_dir = os.path.join(args.output_dir, "json")
    pdf_dir = os.path.join(args.output_dir, "pdf")

    ingested = []
    failed = []

    for i, result in enumerate(search_results):
        doi = result["doi"]
        status = ingest_article(
            doi=doi,
            json_dir=json_dir,
            pdf_dir=pdf_dir,
            skip_pdf=args.skip_pdf,
        )
        if status["success"]:
            ingested.append(status)
        else:
            failed.append(status)

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("SEED DATABASE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Articles ingested: {len(ingested)}/{len(search_results)}")
    logger.info(f"Output directory: {args.output_dir}/")
    logger.info(f"  - Metadata: {json_dir}/")
    if not args.skip_pdf:
        logger.info(f"  - PDFs: {pdf_dir}/")

    # Save final report
    report = {
        "timestamp": datetime.now().isoformat(),
        "query": args.query,
        "search_results_total": results["summary"]["total_unique"],
        "articles_requested": len(search_results),
        "articles_ingested": len(ingested),
        "articles_failed": len(failed),
        "success_rate": round(len(ingested) / len(search_results) * 100, 1)
        if search_results
        else 0,
    }
    report_path = os.path.join(args.output_dir, "seed_db_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Build a seed database of articles on a topic.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Search only
  python -m eu_fact_force.ingestion.data_collection.seed_db search \\
    --query "vaccine autism" --output-dir ./vax_autism

  # Full pipeline: search + ingest 50 articles
  python -m eu_fact_force.ingestion.data_collection.seed_db full \\
    --query "vaccine autism" \\
    --output-dir ./vax_autism \\
    --max-articles 50

  # Ingest already-searched results
  python -m eu_fact_force.ingestion.data_collection.seed_db ingest \\
    --search-results ./vax_autism/search_results.json \\
    --output-dir ./vax_autism \\
    --max-articles 50 \\
    --skip-pdf
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for articles")
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument(
        "--output-dir", default="./seed_db", help="Output directory"
    )
    search_parser.add_argument(
        "--max-results", type=int, default=100, help="Max results per source"
    )
    search_parser.add_argument("--min-year", type=int, help="Filter to year onwards")
    search_parser.set_defaults(func=cmd_search)

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest from search results")
    ingest_parser.add_argument(
        "--search-results", required=True, help="Path to search_results.json"
    )
    ingest_parser.add_argument(
        "--output-dir", default="./seed_db", help="Output directory"
    )
    ingest_parser.add_argument(
        "--max-articles", type=int, help="Max articles to ingest"
    )
    ingest_parser.add_argument(
        "--skip-pdf", action="store_true", help="Skip PDF download"
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    # Full pipeline command
    full_parser = subparsers.add_parser("full", help="Search + ingest (full pipeline)")
    full_parser.add_argument("--query", required=True, help="Search query")
    full_parser.add_argument(
        "--output-dir", default="./seed_db", help="Output directory"
    )
    full_parser.add_argument(
        "--max-results", type=int, default=100, help="Max results per source"
    )
    full_parser.add_argument(
        "--max-articles", type=int, help="Max articles to ingest (from search results)"
    )
    full_parser.add_argument(
        "--min-year", type=int, help="Filter to year onwards"
    )
    full_parser.add_argument(
        "--skip-pdf", action="store_true", help="Skip PDF download"
    )
    full_parser.set_defaults(func=cmd_full)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
