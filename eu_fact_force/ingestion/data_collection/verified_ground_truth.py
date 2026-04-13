"""
Find papers with VERIFIED ground truth only.

Sources:
  - arXiv: Official LaTeX source (human-created, verified)
  - bioRxiv/medRxiv: Official HTML + PDF (published by authors)
  - PLOS: Structured XML from peer-reviewed journals

NO extracted/derived text. Only official published versions.
"""

import csv
import json
import logging
from typing import Optional
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ArxivVerified:
    """arXiv papers - LaTeX source is ground truth."""

    def __init__(self, arxiv_id: str, title: str = "", category: str = ""):
        self.arxiv_id = arxiv_id
        self.title = title
        self.category = category
        self.source = "arxiv"
        self.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        self.source_url = f"https://arxiv.org/src/{arxiv_id}"
        self.ground_truth_format = "arxiv_latex_source"

    def to_dict(self):
        return {
            "article_id": f"arxiv:{self.arxiv_id}",
            "title": self.title,
            "source": self.source,
            "ground_truth_format": self.ground_truth_format,
            "pdf_url": self.pdf_url,
            "source_url": self.source_url,
            "verification": "Official arXiv LaTeX source (authors' original)",
        }


class BioRxivVerified:
    """bioRxiv/medRxiv papers - Official HTML is ground truth."""

    def __init__(
        self,
        biorxiv_id: str,
        title: str = "",
        server: str = "biorxiv",
    ):
        self.biorxiv_id = biorxiv_id
        self.title = title
        self.server = server  # "biorxiv" or "medrxiv"
        self.source = server
        self.pdf_url = f"https://www.{server}.org/content/{biorxiv_id}.full.pdf"
        self.html_url = f"https://www.{server}.org/content/{biorxiv_id}.v1.full"
        self.ground_truth_format = "biorxiv_html"

    def to_dict(self):
        return {
            "article_id": f"{self.server}:{self.biorxiv_id}",
            "title": self.title,
            "source": self.source,
            "ground_truth_format": self.ground_truth_format,
            "pdf_url": self.pdf_url,
            "source_url": self.html_url,
            "verification": f"Official {self.server.capitalize()} HTML (published preprint)",
        }


class VerifiedGroundTruthCollector:
    """Collect papers with verified, official ground truth."""

    def __init__(self):
        self.arxiv_base = "https://arxiv.org/api/query"

    def search_arxiv_vaccine_autism(self, limit: int = 30) -> list[ArxivVerified]:
        """
        Search arXiv for vaccine-autism papers.

        Ground truth: Official LaTeX source from authors
        """
        logger.info("\n" + "=" * 60)
        logger.info("Searching arXiv for vaccine-autism papers")
        logger.info("Ground truth: Official LaTeX source")
        logger.info("=" * 60)

        # Broader arXiv search across multiple categories
        query = (
            'cat:(q-bio.QM OR q-bio.CB OR stat.AP OR cs.CY) AND '
            '(abs:"vaccine" AND abs:"autism" OR '
            'abs:"vaccination" AND abs:"autism spectrum" OR '
            'abs:"vaccine safety" AND abs:"autism")'
        )

        params = {
            "search_query": query,
            "max_results": limit * 2,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            response = requests.get(self.arxiv_base, params=params, timeout=30)
            response.raise_for_status()

            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)
            articles = []

            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                try:
                    arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text
                    arxiv_id = arxiv_id.split("/abs/")[-1]

                    title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                    title = title_elem.text.replace("\n", " ") if title_elem is not None else ""

                    article = ArxivVerified(arxiv_id, title)
                    articles.append(article)
                    logger.info(f"  ✓ {arxiv_id}: {title[:70]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse arXiv entry: {e}")
                    continue

            logger.info(f"Found {len(articles)} arXiv papers with vaccine-autism")
            return articles[:limit]

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def search_arxiv_other(self, limit: int = 30) -> list[ArxivVerified]:
        """Search arXiv for other biomedical papers."""
        logger.info("\n" + "=" * 60)
        logger.info("Searching arXiv for other biomedical papers")
        logger.info("Ground truth: Official LaTeX source")
        logger.info("=" * 60)

        query = (
            'cat:(q-bio.QM OR stat.AP) AND '
            '(abs:"clinical trial" OR abs:"efficacy" OR '
            'abs:"treatment" OR abs:"disease") '
            'NOT vaccine'
        )

        params = {
            "search_query": query,
            "max_results": limit * 2,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            response = requests.get(self.arxiv_base, params=params, timeout=30)
            response.raise_for_status()

            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)
            articles = []

            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                try:
                    arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text
                    arxiv_id = arxiv_id.split("/abs/")[-1]

                    title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                    title = title_elem.text.replace("\n", " ") if title_elem is not None else ""

                    article = ArxivVerified(arxiv_id, title)
                    articles.append(article)
                    logger.info(f"  ✓ {arxiv_id}: {title[:70]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse: {e}")
                    continue

            logger.info(f"Found {len(articles)} arXiv papers (other biomedical)")
            return articles[:limit]

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def search_biorxiv_vaccine_autism(self, limit: int = 15) -> list[BioRxivVerified]:
        """
        Search bioRxiv for vaccine-autism papers.

        Ground truth: Official published HTML
        """
        logger.info("\n" + "=" * 60)
        logger.info("Searching bioRxiv for vaccine-autism preprints")
        logger.info("Ground truth: Official bioRxiv HTML")
        logger.info("=" * 60)

        # bioRxiv API is limited, using direct search
        # Format: /search/{query}?format=json
        search_query = "vaccine autism"

        try:
            # Search bioRxiv directly
            search_url = f"https://www.biorxiv.org/search/{search_query}?format=json"
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()

            data = response.json()
            articles = []

            # Parse results
            for result in data.get("articles", [])[:limit]:
                try:
                    # Extract bioRxiv ID from URL
                    # Format: https://www.biorxiv.org/content/10.1101/YYYY.MM.DD.XXXXX
                    biorxiv_id = result.get("doi", "").replace("10.1101/", "")
                    title = result.get("title", "")

                    if biorxiv_id:
                        article = BioRxivVerified(biorxiv_id, title, "biorxiv")
                        articles.append(article)
                        logger.info(f"  ✓ {biorxiv_id}: {title[:70]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse bioRxiv result: {e}")
                    continue

            logger.info(f"Found {len(articles)} bioRxiv papers with vaccine-autism")
            return articles

        except Exception as e:
            logger.warning(f"bioRxiv search limited: {e}")
            logger.info("  (bioRxiv API is limited, using arXiv instead)")
            return []

    def search_medrxiv_vaccine_autism(self, limit: int = 15) -> list[BioRxivVerified]:
        """Search medRxiv for vaccine-related papers."""
        logger.info("\n" + "=" * 60)
        logger.info("Searching medRxiv for vaccine papers")
        logger.info("Ground truth: Official medRxiv HTML")
        logger.info("=" * 60)

        search_query = "vaccine"

        try:
            search_url = f"https://www.medrxiv.org/search/{search_query}?format=json"
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()

            data = response.json()
            articles = []

            for result in data.get("articles", [])[:limit]:
                try:
                    medrxiv_id = result.get("doi", "").replace("10.1101/", "")
                    title = result.get("title", "")

                    if medrxiv_id:
                        article = BioRxivVerified(medrxiv_id, title, "medrxiv")
                        articles.append(article)
                        logger.info(f"  ✓ {medrxiv_id}: {title[:70]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse: {e}")
                    continue

            logger.info(f"Found {len(articles)} medRxiv papers")
            return articles

        except Exception as e:
            logger.warning(f"medRxiv search limited: {e}")
            return []


def collect(output_csv: str = "verified_ground_truth.csv"):
    """Collect papers with VERIFIED ground truth only."""
    logger.info("=" * 60)
    logger.info("COLLECTING PAPERS WITH VERIFIED GROUND TRUTH")
    logger.info("=" * 60)
    logger.info("Sources: arXiv (LaTeX) + bioRxiv/medRxiv (HTML)")
    logger.info("Ground truth: Official, author-created versions")
    logger.info("")

    collector = VerifiedGroundTruthCollector()

    # Search arXiv (most reliable)
    arxiv_vaccine = collector.search_arxiv_vaccine_autism(limit=30)
    arxiv_other = collector.search_arxiv_other(limit=30)

    # Try bioRxiv/medRxiv (limited API)
    biorxiv_vaccine = collector.search_biorxiv_vaccine_autism(limit=15)
    medrxiv_vaccine = collector.search_medrxiv_vaccine_autism(limit=15)

    # Combine all
    all_articles = []
    for article in arxiv_vaccine:
        all_articles.append({"category": "vaccine_autism", "article": article})
    for article in arxiv_other:
        all_articles.append({"category": "other", "article": article})
    for article in biorxiv_vaccine:
        all_articles.append({"category": "vaccine_autism", "article": article})
    for article in medrxiv_vaccine:
        all_articles.append({"category": "vaccine_autism", "article": article})

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Vaccine-autism: {len(arxiv_vaccine) + len(biorxiv_vaccine) + len(medrxiv_vaccine)}")
    logger.info(f"  - arXiv: {len(arxiv_vaccine)}")
    logger.info(f"  - bioRxiv: {len(biorxiv_vaccine)}")
    logger.info(f"  - medRxiv: {len(medrxiv_vaccine)}")
    logger.info(f"Other: {len(arxiv_other)}")
    logger.info(f"  - arXiv: {len(arxiv_other)}")
    logger.info(f"Total: {len(all_articles)}")

    # Save CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "category",
            "article_id",
            "title",
            "source",
            "ground_truth_format",
            "pdf_url",
            "source_url",
            "verification",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in all_articles:
            row = item["article"].to_dict()
            row["category"] = item["category"]
            writer.writerow(row)

    logger.info(f"\n✓ Saved {len(all_articles)} papers to {output_csv}")
    logger.info(f"  Ground truth: Official, author-created versions")
    logger.info(f"  Next: Download PDFs + ground truth sources")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Find papers with verified ground truth only"
    )
    parser.add_argument(
        "--output-csv",
        default="verified_ground_truth.csv",
        help="Output CSV file",
    )

    args = parser.parse_args()
    collect(args.output_csv)
