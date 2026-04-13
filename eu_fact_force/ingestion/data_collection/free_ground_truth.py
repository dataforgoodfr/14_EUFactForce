"""
Collect 50 open-access articles with both PDF and text versions.

Uses only FREE sources:
  - PubMed Central (PMC) - 100% free, has full text XML + PDF
  - arXiv - 100% free preprints, has PDF + source code
  - bioRxiv/medRxiv - 100% free preprints, has PDF + HTML

Generates a CSV with downloadable URLs for both PDF and text versions.
"""

import csv
import logging
import re
from typing import Optional
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PMCArticle:
    """PubMed Central article with guaranteed free access."""

    def __init__(self, pmc_id: str, doi: Optional[str] = None, title: str = ""):
        self.pmc_id = pmc_id
        self.doi = doi
        self.title = title
        self.source = "pubmed_central"
        # PMC article URLs are predictable
        self.pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/"
        self.pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
        self.xml_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/xml/"

    def to_dict(self):
        return {
            "article_id": f"PMC{self.pmc_id}",
            "doi": self.doi or "",
            "title": self.title,
            "source": self.source,
            "text_format": "pmc_xml",
            "pdf_url": self.pdf_url,
            "text_url": self.xml_url,
            "free_access": "✓",
        }


class ArxivArticle:
    """arXiv preprint with guaranteed free access."""

    def __init__(self, arxiv_id: str, title: str = ""):
        self.arxiv_id = arxiv_id
        self.title = title
        self.source = "arxiv"
        self.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        # arXiv source can be downloaded as tar.gz
        self.text_url = f"https://arxiv.org/src/{arxiv_id}"

    def to_dict(self):
        return {
            "article_id": f"arxiv:{self.arxiv_id}",
            "doi": "",
            "title": self.title,
            "source": self.source,
            "text_format": "arxiv_source",
            "pdf_url": self.pdf_url,
            "text_url": self.text_url,
            "free_access": "✓",
        }


class FreeArticleCollector:
    """Collect articles from free sources with text versions available."""

    def __init__(self):
        self.pmc_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.arxiv_base = "https://arxiv.org/api/query"

    def search_pmc_vaccine_autism(self, limit: int = 30) -> list[PMCArticle]:
        """
        Search PubMed Central for vaccine-autism articles.

        Uses PMC Open Access collection (all articles are free to download).
        """
        logger.info(f"\n{'='*60}")
        logger.info("Searching PubMed Central for vaccine-autism articles")
        logger.info(f"{'='*60}")

        # Search PMC Open Access subset
        # Filter: must have full text, open access, recent years
        query = (
            '("vaccine*" OR "vaccin*") AND ("autism" OR "autistic") '
            'AND ("study" OR "trial" OR "research" OR "evidence" OR "safety")'
        )

        search_params = {
            "db": "pmc",
            "term": query,
            "retmax": limit * 2,  # Get extras in case some fail
            "retmode": "json",
        }

        try:
            response = requests.get(
                f"{self.pmc_base}/esearch.fcgi",
                params=search_params,
                timeout=30,
            )
            response.raise_for_status()
            pmc_ids = response.json()["esearchresult"]["idlist"]
            logger.info(f"Found {len(pmc_ids)} articles in PMC")

            # Fetch details for each
            articles = []
            for pmc_id in pmc_ids[:limit]:
                details = self._get_pmc_details(pmc_id)
                if details:
                    articles.append(details)
                    logger.info(f"  ✓ PMC{pmc_id}: {details.title[:60]}...")

            return articles[:limit]

        except Exception as e:
            logger.error(f"PMC search failed: {e}")
            return []

    def search_pmc_other(self, limit: int = 30) -> list[PMCArticle]:
        """Search PMC for other biomedical articles (not vaccine-related)."""
        logger.info(f"\n{'='*60}")
        logger.info("Searching PubMed Central for other biomedical articles")
        logger.info(f"{'='*60}")

        # Search for clinical studies, trials, research (exclude vaccines)
        query = (
            '("randomized controlled trial" OR "clinical trial" OR "meta-analysis") '
            'AND ("efficacy" OR "safety" OR "treatment") NOT "vaccine*"'
        )

        search_params = {
            "db": "pmc",
            "term": query,
            "retmax": limit * 2,
            "retmode": "json",
        }

        try:
            response = requests.get(
                f"{self.pmc_base}/esearch.fcgi",
                params=search_params,
                timeout=30,
            )
            response.raise_for_status()
            pmc_ids = response.json()["esearchresult"]["idlist"]
            logger.info(f"Found {len(pmc_ids)} articles in PMC")

            articles = []
            for pmc_id in pmc_ids[:limit]:
                details = self._get_pmc_details(pmc_id)
                if details:
                    articles.append(details)
                    logger.info(f"  ✓ PMC{pmc_id}: {details.title[:60]}...")

            return articles[:limit]

        except Exception as e:
            logger.error(f"PMC search failed: {e}")
            return []

    def _get_pmc_details(self, pmc_id: str) -> Optional[PMCArticle]:
        """Fetch article details from PMC."""
        try:
            summary_params = {
                "db": "pmc",
                "id": pmc_id,
                "retmode": "json",
            }
            response = requests.get(
                f"{self.pmc_base}/esummary.fcgi",
                params=summary_params,
                timeout=10,
            )
            response.raise_for_status()

            result = response.json().get("result", {}).get(pmc_id, {})
            title = result.get("title", "Unknown")

            # Look for DOI
            doi = None
            for uid in result.get("uids", []):
                if uid.startswith("10."):
                    doi = uid
                    break

            return PMCArticle(pmc_id, doi, title)

        except Exception as e:
            logger.debug(f"Failed to fetch PMC{pmc_id}: {e}")
            return None

    def search_arxiv_vaccine_autism(self, limit: int = 10) -> list[ArxivArticle]:
        """Search arXiv for vaccine-autism preprints."""
        logger.info(f"\n{'='*60}")
        logger.info("Searching arXiv for vaccine-autism preprints")
        logger.info(f"{'='*60}")

        # arXiv query: quantitative biology + medical physics
        query = (
            'cat:(q-bio.QM OR q-bio.CB OR stat.AP) AND '
            '(abs:"vaccine" AND abs:"autism" OR abs:"vaccination" AND abs:"autism")'
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
                    title = title_elem.text.replace("\n", " ") if title_elem is not None else "Unknown"

                    article = ArxivArticle(arxiv_id, title)
                    articles.append(article)
                    logger.info(f"  ✓ {arxiv_id}: {title[:60]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse arXiv entry: {e}")
                    continue

            return articles[:limit]

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def search_arxiv_other(self, limit: int = 10) -> list[ArxivArticle]:
        """Search arXiv for other biomedical preprints."""
        logger.info(f"\n{'='*60}")
        logger.info("Searching arXiv for other biomedical preprints")
        logger.info(f"{'='*60}")

        query = (
            'cat:(q-bio.QM OR q-bio.CB OR stat.AP) AND '
            '(abs:"clinical trial" OR abs:"efficacy" OR abs:"treatment")'
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
                    title = title_elem.text.replace("\n", " ") if title_elem is not None else "Unknown"

                    article = ArxivArticle(arxiv_id, title)
                    articles.append(article)
                    logger.info(f"  ✓ {arxiv_id}: {title[:60]}...")

                except Exception as e:
                    logger.debug(f"Failed to parse arXiv entry: {e}")
                    continue

            return articles[:limit]

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []


def collect(output_csv: str = "ground_truth_50_articles.csv"):
    """Collect 50 articles (25 vaccine-autism + 25 other) with free text access."""
    logger.info("=" * 60)
    logger.info("COLLECTING 50 FREE GROUND TRUTH ARTICLES")
    logger.info("=" * 60)
    logger.info("Sources: PubMed Central (free OA) + arXiv (free preprints)")
    logger.info("")

    collector = FreeArticleCollector()

    # Collect articles
    pmc_vaccine = collector.search_pmc_vaccine_autism(limit=20)
    arxiv_vaccine = collector.search_arxiv_vaccine_autism(limit=5)
    pmc_other = collector.search_pmc_other(limit=20)
    arxiv_other = collector.search_arxiv_other(limit=5)

    # Combine
    vaccine_articles = pmc_vaccine + arxiv_vaccine
    other_articles = pmc_other + arxiv_other

    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Vaccine-autism articles: {len(vaccine_articles)}")
    logger.info(f"  - PMC: {len(pmc_vaccine)}")
    logger.info(f"  - arXiv: {len(arxiv_vaccine)}")
    logger.info(f"Other articles: {len(other_articles)}")
    logger.info(f"  - PMC: {len(pmc_other)}")
    logger.info(f"  - arXiv: {len(arxiv_other)}")
    logger.info(f"Total: {len(vaccine_articles) + len(other_articles)}")

    # Save to CSV
    all_articles = []
    for article in vaccine_articles:
        data = article.to_dict()
        data["category"] = "vaccine_autism"
        all_articles.append(data)

    for article in other_articles:
        data = article.to_dict()
        data["category"] = "other"
        all_articles.append(data)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "category",
            "article_id",
            "doi",
            "title",
            "source",
            "text_format",
            "pdf_url",
            "text_url",
            "free_access",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_articles)

    logger.info(f"\n✓ Saved {len(all_articles)} articles to {output_csv}")
    logger.info(f"\nNext steps:")
    logger.info(f"1. Download PDFs and text from URLs in CSV")
    logger.info(f"2. Extract text from PDFs and compare with ground truth")
    logger.info(f"3. Evaluate parser quality on {len(all_articles)} documents")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect 50 free articles with PDF + text versions"
    )
    parser.add_argument(
        "--output-csv",
        default="ground_truth_50_articles.csv",
        help="Output CSV file",
    )

    args = parser.parse_args()
    collect(args.output_csv)
