"""
Batch ingest articles from a search results JSON file.

Usage:
    python -m eu_fact_force.ingestion.data_collection.batch_ingest \
        --search-results search_results.json \
        --output-dir ./seed_db \
        --max-articles 50
"""

import argparse
import json
import logging
import os
from pathlib import Path

from eu_fact_force.ingestion.data_collection.collector import fetch_all
from eu_fact_force.ingestion.data_collection.parsers import PARSERS
from eu_fact_force.ingestion.data_collection.parsers.base import doi_to_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_search_results(json_path: str) -> list[dict]:
    """Load search results from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", [])


def ingest_article(
    doi: str,
    json_dir: str,
    pdf_dir: str,
    skip_pdf: bool = False,
    timeout_seconds: int = 30,
) -> dict:
    """
    Ingest a single article by DOI.

    Args:
        doi: Article DOI
        json_dir: Directory to save metadata JSON
        pdf_dir: Directory to save PDFs
        skip_pdf: Skip PDF download if True
        timeout_seconds: Timeout for PDF downloads

    Returns:
        Status dict with success, doi, filename, error message
    """
    article_id = doi_to_id(doi)
    json_path = os.path.join(json_dir, f"{article_id}.json")

    # Skip if already ingested
    if os.path.exists(json_path):
        logger.info(f"[SKIP] {doi} already ingested")
        return {"success": False, "doi": doi, "reason": "already_ingested"}

    try:
        # Fetch metadata from all available sources
        logger.info(f"[FETCH] {doi}")
        metadata = {"id": article_id} | fetch_all(doi)

        # Save metadata
        os.makedirs(json_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"[SAVED] Metadata: {json_path}")

        pdf_file = None
        if not skip_pdf:
            # Try to download PDF
            os.makedirs(pdf_dir, exist_ok=True)
            for parser in PARSERS:
                try:
                    if parser.download_pdf(doi, pdf_dir):
                        pdf_file = os.path.join(
                            pdf_dir, f"{article_id}_{parser.api_name}.pdf"
                        )
                        file_size = os.path.getsize(pdf_file)
                        logger.info(f"[PDF] {pdf_file} ({file_size:,} bytes)")
                        break
                except Exception as e:
                    logger.debug(f"{parser.__class__.__name__} PDF error: {e}")
            if not pdf_file:
                logger.warning(f"[PDF SKIP] {doi} - no PDF found")

        return {
            "success": True,
            "doi": doi,
            "article_id": article_id,
            "metadata_file": json_path,
            "pdf_file": pdf_file,
        }

    except Exception as e:
        logger.error(f"[ERROR] {doi}: {e}")
        return {
            "success": False,
            "doi": doi,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Batch ingest articles from search results."
    )
    parser.add_argument(
        "--search-results",
        required=True,
        help="Path to search results JSON file",
    )
    parser.add_argument(
        "--output-dir",
        default="./seed_db",
        help="Base directory for output (creates json/ and pdf/ subdirs)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Maximum articles to ingest (default: all)",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF download (metadata only)",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=0,
        help="Start at this index (for resuming)",
    )
    args = parser.parse_args()

    # Load search results
    results = load_search_results(args.search_results)
    logger.info(f"Loaded {len(results)} search results")

    if args.max_articles:
        results = results[: args.max_articles]
        logger.info(f"Limited to {len(results)} articles")

    results = results[args.start_at :]
    logger.info(f"Starting at index {args.start_at}, {len(results)} remaining")

    # Setup directories
    json_dir = os.path.join(args.output_dir, "json")
    pdf_dir = os.path.join(args.output_dir, "pdf")

    # Ingest each article
    ingested = []
    failed = []
    for i, result in enumerate(results):
        doi = result["doi"]
        logger.info(f"\n[{i+1}/{len(results)}] Processing {doi}")

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
    logger.info(f"INGESTION COMPLETE")
    logger.info(f"  Successful: {len(ingested)}")
    logger.info(f"  Failed: {len(failed)}")
    logger.info(f"  Output: {args.output_dir}")

    if failed:
        logger.warning(f"\nFailed articles ({len(failed)}):")
        for f in failed:
            logger.warning(f"  - {f['doi']}: {f.get('error', f.get('reason', 'unknown'))}")

    # Save ingestion manifest
    manifest = {
        "search_file": args.search_results,
        "total_input": len(results),
        "successful": len(ingested),
        "failed": len(failed),
        "output_dir": args.output_dir,
        "ingested": ingested,
        "failed": failed,
    }
    manifest_path = os.path.join(args.output_dir, "ingestion_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Manifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
