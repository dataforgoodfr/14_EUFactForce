"""
Collect verified ground truth articles from arXiv.

"Verified" means the ground truth text is the official LaTeX source that the
authors submitted — not extracted from a PDF. This gives clean, artifact-free
reference text for parser quality evaluation.

Usage:
    python -m eu_fact_force.ingestion.data_collection.ground_truth \\
        --output verified_ground_truth.csv \\
        --vaccine-limit 30 \\
        --other-limit 30
"""

import argparse
import csv
import logging
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_ARXIV_API = "https://arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"

CSV_FIELDS = [
    "category",
    "article_id",
    "title",
    "source",
    "ground_truth_format",
    "pdf_url",
    "text_url",
    "verification",
]


@dataclass
class ArxivGroundTruth:
    arxiv_id: str
    title: str
    category: str   # "vaccine_autism" | "other"

    @property
    def article_id(self) -> str:
        return f"arxiv:{self.arxiv_id}"

    @property
    def pdf_url(self) -> str:
        return f"https://arxiv.org/pdf/{self.arxiv_id}.pdf"

    @property
    def text_url(self) -> str:
        # Official LaTeX source archive
        return f"https://arxiv.org/src/{self.arxiv_id}"

    def to_row(self) -> dict:
        return {
            "category": self.category,
            "article_id": self.article_id,
            "title": self.title,
            "source": "arxiv",
            "ground_truth_format": "arxiv_latex_source",
            "pdf_url": self.pdf_url,
            "text_url": self.text_url,
            "verification": "Official arXiv LaTeX source (authors' original)",
        }


class ArxivGroundTruthCollector:
    """Query the arXiv Atom API and return ArxivGroundTruth records."""

    def search(
        self,
        query: str,
        category: str,
        limit: int,
    ) -> list[ArxivGroundTruth]:
        params = {
            "search_query": query,
            "max_results": limit * 2,  # fetch extra to account for parse failures
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            resp = requests.get(_ARXIV_API, params=params, timeout=30)
            resp.raise_for_status()
        except Exception:
            logger.exception("arxiv.request_failed query=%s", query[:60])
            return []

        root = ET.fromstring(resp.content)
        articles: list[ArxivGroundTruth] = []

        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            try:
                arxiv_id = _parse_arxiv_id(entry)
                title = _parse_title(entry)
                if arxiv_id and title:
                    articles.append(ArxivGroundTruth(arxiv_id, title, category))
                    logger.debug("arxiv.found id=%s title=%s", arxiv_id, title[:60])
            except Exception as e:
                logger.debug("arxiv.parse_error error=%s", e)

        result = articles[:limit]
        logger.info("arxiv.search_done query=%s found=%d", query[:60], len(result))
        return result


def collect(
    output_csv: str,
    vaccine_limit: int = 30,
    other_limit: int = 30,
) -> list[ArxivGroundTruth]:
    """
    Collect verified ground truth articles and write to a CSV.

    Searches for two categories:
      - vaccine_autism: papers on vaccine safety / autism link
      - other: general biomedical / ML-in-health papers (as contrast set)

    Returns the list of collected articles.
    """
    collector = ArxivGroundTruthCollector()

    vaccine_query = (
        'cat:(q-bio.QM OR q-bio.CB OR stat.AP OR cs.CY) AND '
        '(abs:"vaccine" AND abs:"autism" OR '
        'abs:"vaccination" AND abs:"autism spectrum" OR '
        'abs:"vaccine safety" AND abs:"autism")'
    )
    other_query = (
        'cat:(q-bio.QM OR stat.AP) AND '
        '(abs:"clinical trial" OR abs:"efficacy" OR abs:"treatment") '
        'NOT abs:vaccine'
    )

    vaccine_articles = collector.search(vaccine_query, "vaccine_autism", vaccine_limit)
    other_articles = collector.search(other_query, "other", other_limit)

    all_articles = vaccine_articles + other_articles

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for article in all_articles:
            writer.writerow(article.to_row())

    logger.info(
        "ground_truth.saved csv=%s vaccine=%d other=%d total=%d",
        output_csv, len(vaccine_articles), len(other_articles), len(all_articles),
    )
    print(f"Saved {len(all_articles)} articles to {output_csv}")
    print(f"  vaccine_autism : {len(vaccine_articles)}")
    print(f"  other          : {len(other_articles)}")
    return all_articles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_arxiv_id(entry: ET.Element) -> Optional[str]:
    id_elem = entry.find(f"{{{_ATOM_NS}}}id")
    if id_elem is None or not id_elem.text:
        return None
    # URL form: https://arxiv.org/abs/2301.00001v1
    return id_elem.text.strip().split("/abs/")[-1]


def _parse_title(entry: ET.Element) -> Optional[str]:
    title_elem = entry.find(f"{{{_ATOM_NS}}}title")
    if title_elem is None or not title_elem.text:
        return None
    return " ".join(title_elem.text.split())  # normalise whitespace


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="verified_ground_truth.csv")
    parser.add_argument("--vaccine-limit", type=int, default=30)
    parser.add_argument("--other-limit", type=int, default=30)
    args = parser.parse_args()

    articles = collect(args.output, args.vaccine_limit, args.other_limit)
    if not articles:
        print("No articles collected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
