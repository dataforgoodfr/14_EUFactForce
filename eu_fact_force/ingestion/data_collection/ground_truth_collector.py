"""
Collect articles with both PDF and alternative text versions available.

Focuses on sources with guaranteed open access + downloadable text:
  - PubMed Central (XML full text + PDF)
  - arXiv (PDF + text extraction)
  - bioRxiv/medRxiv (PDF + HTML)

Usage:
    python ground_truth_collector.py \
        --query "vaccine autism" \
        --output-csv ground_truth_dois.csv \
        --target 50 \
        --text-format pmc  # pmc, arxiv, or any
"""

import csv
import json
import logging
import re
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PMCSearcher:
    """Search PubMed Central for open access articles with full text."""

    def __init__(self):
        self.search_url = "https://www.ncbi.nlm.nih.gov/research/pmc/utils/apikey"
        self.search_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/webenv"
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.pmc_base = "https://www.ncbi.nlm.nih.gov/pmc/articles"

    def search(self, query: str, max_results: int = 100) -> list[dict]:
        """
        Search PMC for open access articles.

        Args:
            query: Search terms
            max_results: Max articles to return

        Returns:
            List of {pmc_id, pmid, doi, title, authors, pub_date, pdf_url, xml_url}
        """
        # Search PMC (open access only)
        search_params = {
            "db": "pmc",
            "term": f"{query} AND open access[FILT]",
            "retmax": max_results,
            "retmode": "json",
        }

        logger.info(f"Searching PMC: {query}")
        try:
            response = requests.get(
                f"{self.base_url}/esearch.fcgi",
                params=search_params,
                timeout=30,
            )
            response.raise_for_status()
            ids = response.json()["esearchresult"]["idlist"]
            logger.info(f"Found {len(ids)} PMC articles")

            # Fetch details for each article
            results = []
            for pmc_id in ids[:max_results]:
                details = self._fetch_article_details(pmc_id)
                if details:
                    results.append(details)

            return results

        except Exception as e:
            logger.error(f"PMC search failed: {e}")
            return []

    def _fetch_article_details(self, pmc_id: str) -> Optional[dict]:
        """Fetch article details from PMC."""
        try:
            # Get article metadata
            meta_url = f"{self.pmc_base}/{pmc_id}/"
            response = requests.get(meta_url, timeout=10)

            if response.status_code != 200:
                return None

            # Extract DOI from page or API
            # PMC articles have predictable URLs for PDF and XML
            pdf_url = f"{self.pmc_base}/{pmc_id}/pdf/"
            xml_url = f"{self.pmc_base}/{pmc_id}/xml/"

            # Try to get DOI
            doi = None
            doi_match = re.search(r"doi[:\s]+([0-9.]+/[^\s<]+)", response.text, re.IGNORECASE)
            if doi_match:
                doi = doi_match.group(1)

            # Try to get basic metadata from page
            title_match = re.search(r"<h1[^>]*>([^<]+)</h1>", response.text)
            title = title_match.group(1).strip() if title_match else "Unknown"

            return {
                "pmc_id": pmc_id,
                "doi": doi,
                "title": title,
                "pdf_url": pdf_url,
                "text_url": xml_url,
                "text_format": "pmc_xml",
                "source": "pubmed_central",
            }

        except Exception as e:
            logger.debug(f"Failed to fetch PMC {pmc_id}: {e}")
            return None


class ArxivSearcher:
    """Search arXiv for papers with PDFs and source available."""

    def __init__(self):
        self.base_url = "http://arxiv.org/api/query"

    def search(self, query: str, max_results: int = 100, category: str = "q-bio") -> list[dict]:
        """
        Search arXiv for papers.

        Args:
            query: Search terms
            max_results: Max papers to return
            category: arXiv category (q-bio.QM = quantitative biology, med-ph = medical physics, etc)

        Returns:
            List of {arxiv_id, doi, title, authors, pub_date, pdf_url, text_url}
        """
        # arXiv query: search in abstract + title, filter by category
        arxiv_query = f"cat:{category} AND (abs:{query} OR ti:{query})"

        params = {
            "search_query": arxiv_query,
            "max_results": min(max_results, 2000),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        logger.info(f"Searching arXiv: {query}")
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            results = []
            # Parse Atom feed
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text.split("/abs/")[-1]
                title = entry.find("{http://www.w3.org/2005/Atom}title").text
                published = entry.find("{http://www.w3.org/2005/Atom}published").text

                # Look for DOI
                doi = None
                doi_elem = entry.find(
                    "{http://arxiv.org/schemas/atom}doi}"
                )
                if doi_elem is not None:
                    doi = doi_elem.text

                # arXiv PDF and source URLs
                pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf"
                source_url = f"http://arxiv.org/src/{arxiv_id}"

                results.append(
                    {
                        "arxiv_id": arxiv_id,
                        "doi": doi,
                        "title": title.replace("\n ", " "),
                        "pdf_url": pdf_url,
                        "text_url": source_url,
                        "text_format": "arxiv_source_tar",
                        "source": "arxiv",
                    }
                )

            logger.info(f"Found {len(results)} arXiv papers")
            return results

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []


class BioRxivSearcher:
    """Search bioRxiv/medRxiv for preprints with PDFs and HTML."""

    def __init__(self):
        self.api_url = "https://api.biorxiv.org/details"

    def search(self, query: str, max_results: int = 100, server: str = "biorxiv") -> list[dict]:
        """
        Search bioRxiv/medRxiv.

        Args:
            query: Search terms
            max_results: Max results
            server: "biorxiv" or "medrxiv"

        Returns:
            List of articles with PDFs and HTML text
        """
        # bioRxiv API: search by category/date
        # This is a simplified version - actual API has limited search
        logger.info(f"bioRxiv search not fully implemented (API limitations)")
        logger.info("Recommend manual search at biorxiv.org or medrxiv.org")
        return []


def collect_ground_truth(
    vaccines_query: str = "vaccine autism",
    other_query: str = "clinical trial biomedical",
    target_vaccines: int = 25,
    target_other: int = 25,
    output_csv: str = "ground_truth_dois.csv",
) -> list[dict]:
    """
    Collect 50 articles with both PDF and text versions available.

    Args:
        vaccines_query: Query for vaccine-autism articles
        other_query: Query for other biomedical articles
        target_vaccines: Number of vaccine articles to collect
        target_other: Number of other articles to collect
        output_csv: Output CSV file path

    Returns:
        List of article dicts
    """
    all_results = []

    # Search PMC for vaccine-autism articles
    logger.info("\n" + "=" * 60)
    logger.info("STEP 1: Searching PMC for vaccine-autism articles")
    logger.info("=" * 60)
    pmc = PMCSearcher()
    vaccine_results = pmc.search(vaccines_query, max_results=target_vaccines * 3)
    logger.info(f"Collected {len(vaccine_results)} vaccine articles from PMC")
    all_results.extend([{**r, "category": "vaccine_autism"} for r in vaccine_results[:target_vaccines]])

    # Search PMC for other biomedical articles
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Searching PMC for other biomedical articles")
    logger.info("=" * 60)
    other_results = pmc.search(other_query, max_results=target_other * 3)
    logger.info(f"Collected {len(other_results)} other articles from PMC")
    all_results.extend([{**r, "category": "other"} for r in other_results[:target_other]])

    # Fallback: Search arXiv for additional articles if needed
    if len([r for r in all_results if r["source"] == "arxiv"]) < 10:
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Searching arXiv for supplemental articles")
        logger.info("=" * 60)
        arxiv = ArxivSearcher()
        arxiv_results = arxiv.search("vaccine autism", max_results=10, category="q-bio.QM")
        logger.info(f"Collected {len(arxiv_results)} arXiv preprints")
        all_results.extend([{**r, "category": "vaccine_autism"} for r in arxiv_results[:5]])

    # Save to CSV
    logger.info("\n" + "=" * 60)
    logger.info(f"SAVING RESULTS TO {output_csv}")
    logger.info("=" * 60)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "category",
            "source",
            "pmc_id",
            "arxiv_id",
            "doi",
            "title",
            "text_format",
            "pdf_url",
            "text_url",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in all_results:
            row = {
                "category": result.get("category"),
                "source": result.get("source"),
                "pmc_id": result.get("pmc_id", ""),
                "arxiv_id": result.get("arxiv_id", ""),
                "doi": result.get("doi", ""),
                "title": result.get("title", ""),
                "text_format": result.get("text_format"),
                "pdf_url": result.get("pdf_url"),
                "text_url": result.get("text_url"),
            }
            writer.writerow(row)

    logger.info(f"✓ Saved {len(all_results)} articles to {output_csv}")
    logger.info(f"  - Vaccine/autism: {len([r for r in all_results if r.get('category') == 'vaccine_autism'])}")
    logger.info(f"  - Other: {len([r for r in all_results if r.get('category') == 'other'])}")

    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect ground truth articles with text versions.")
    parser.add_argument(
        "--vaccines-query",
        default="vaccine autism",
        help="Query for vaccine-autism articles",
    )
    parser.add_argument(
        "--other-query",
        default="clinical trial biomedical",
        help="Query for other articles",
    )
    parser.add_argument(
        "--target-vaccines",
        type=int,
        default=25,
        help="Target number of vaccine articles",
    )
    parser.add_argument(
        "--target-other",
        type=int,
        default=25,
        help="Target number of other articles",
    )
    parser.add_argument(
        "--output-csv",
        default="ground_truth_dois.csv",
        help="Output CSV file",
    )

    args = parser.parse_args()

    results = collect_ground_truth(
        vaccines_query=args.vaccines_query,
        other_query=args.other_query,
        target_vaccines=args.target_vaccines,
        target_other=args.target_other,
        output_csv=args.output_csv,
    )
