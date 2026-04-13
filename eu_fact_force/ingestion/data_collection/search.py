"""
Search for scientific articles on a given topic across PubMed and Crossref.

Supports:
  - Searching by keyword/topic (e.g., "vaccine autism")
  - Filtering by date range, open access preference
  - De-duplicating DOIs across sources
  - Exporting results for batch ingestion
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with metadata."""
    doi: str
    title: str
    authors: list[str]
    pub_date: Optional[str]
    journal: Optional[str]
    source: str  # "pubmed" or "crossref"
    open_access: Optional[bool] = None
    url: Optional[str] = None

    def to_dict(self):
        return {
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "pub_date": self.pub_date,
            "journal": self.journal,
            "source": self.source,
            "open_access": self.open_access,
            "url": self.url,
        }


class PubMedSearcher:
    """Search and retrieve article metadata from PubMed."""

    def __init__(self, email: str = "bot@dataforgood.fr"):
        """
        Initialize PubMed searcher.

        Args:
            email: Contact email for NCBI (required by their API terms)
        """
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        self.email = email
        self.base_params = {"tool": "eu-fact-force", "email": self.email}

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
        sort: str = "relevance",
    ) -> list[SearchResult]:
        """
        Search PubMed for articles.

        Args:
            query: Search term (e.g., "vaccine autism")
            max_results: Maximum articles to retrieve
            min_year: Filter to articles from this year onwards
            sort: Sort by "relevance" (default) or "date"

        Returns:
            List of SearchResult objects
        """
        if min_year:
            query = f"{query} AND {min_year}[PDAT]:3000[PDAT]"

        try:
            # Step 1: Search for article IDs
            search_params = {
                **self.base_params,
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": sort,
            }
            logger.info(f"PubMed search: {query[:60]}... (max={max_results})")
            response = requests.get(self.search_url, params=search_params, timeout=30)
            response.raise_for_status()

            ids = response.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                logger.info("PubMed: No results found.")
                return []
            logger.info(f"PubMed: Found {len(ids)} article IDs")

            # Step 2: Fetch metadata for all IDs
            summary_params = {
                **self.base_params,
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "json",
            }
            response = requests.get(
                self.summary_url, params=summary_params, timeout=30
            )
            response.raise_for_status()

            results = []
            for uid, doc in response.json().get("result", {}).items():
                if uid == "uids":  # Skip metadata row
                    continue

                # Extract DOI
                doi = None
                for aid in doc.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid["value"]
                        break

                if not doi:
                    logger.debug(f"PubMed {uid}: No DOI found, skipping")
                    continue

                # Extract basic metadata
                title = doc.get("title", "")
                authors = [a.get("name", "") for a in doc.get("authors", [])]
                pub_date = doc.get("pubdate")
                journal = doc.get("fulljournalname")

                results.append(
                    SearchResult(
                        doi=doi,
                        title=title,
                        authors=authors,
                        pub_date=pub_date,
                        journal=journal,
                        source="pubmed",
                    )
                )

            logger.info(f"PubMed: Extracted {len(results)} DOIs")
            return results

        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            return []


class CrossrefSearcher:
    """Search and retrieve article metadata from Crossref."""

    def __init__(self):
        self.url = "https://api.crossref.org/works"
        self.headers = {"User-Agent": "eu-fact-force (bot@dataforgood.fr)"}

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
        open_access_only: bool = False,
    ) -> list[SearchResult]:
        """
        Search Crossref for articles.

        Args:
            query: Search term
            max_results: Maximum articles to retrieve
            min_year: Filter to articles from this year onwards
            open_access_only: Only return open access articles

        Returns:
            List of SearchResult objects
        """
        try:
            # Build filters
            filters = []
            if min_year:
                filters.append(f"from-pub-date:{min_year}-01-01")
            if open_access_only:
                filters.append("has-oa:true")

            params = {
                "query": query,
                "rows": max_results,
                "select": "DOI,title,author,published-online,container-title,is-oa",
            }
            if filters:
                params["filter"] = ",".join(filters)

            logger.info(f"Crossref search: {query[:60]}... (max={max_results})")
            response = requests.get(
                self.url, params=params, headers=self.headers, timeout=30
            )
            response.raise_for_status()

            results = []
            items = response.json().get("message", {}).get("items", [])
            logger.info(f"Crossref: Found {len(items)} results")

            for item in items:
                doi = item.get("DOI")
                if not doi:
                    continue

                title = (item.get("title") or [""])[0]
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in item.get("author", [])
                ]
                pub_date = (
                    item.get("published-online", {}).get("date-iso")
                    or item.get("published-print", {}).get("date-iso")
                )
                journal = (item.get("container-title") or [""])[0]
                is_oa = item.get("is-oa")

                results.append(
                    SearchResult(
                        doi=doi,
                        title=title,
                        authors=authors,
                        pub_date=pub_date,
                        journal=journal,
                        source="crossref",
                        open_access=is_oa,
                    )
                )

            logger.info(f"Crossref: Extracted {len(results)} DOIs")
            return results

        except Exception as e:
            logger.error(f"Crossref search failed: {e}")
            return []


class ArticleSearcher:
    """Orchestrate searches across multiple sources and deduplicate results."""

    def __init__(self):
        self.pubmed = PubMedSearcher()
        self.crossref = CrossrefSearcher()

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
        open_access_preferred: bool = True,
    ) -> dict:
        """
        Search for articles on a topic across PubMed and Crossref.

        Args:
            query: Search term (e.g., "vaccine autism")
            max_results: Maximum articles per source
            min_year: Filter to articles from this year onwards
            open_access_preferred: Prioritize open access articles

        Returns:
            Dict with:
              - "results": list of deduplicated SearchResult objects
              - "summary": counts and stats
        """
        logger.info(f"Starting search for: {query}")

        # Search both sources
        pubmed_results = self.pubmed.search(query, max_results, min_year)
        crossref_results = self.crossref.search(query, max_results, min_year, open_access_preferred)

        # Deduplicate by DOI (normalize to lowercase)
        seen = {}
        for result in pubmed_results + crossref_results:
            doi_lower = result.doi.lower()
            if doi_lower not in seen:
                seen[doi_lower] = result
            else:
                # Merge: prefer pubmed if both have source, then prefer open access
                existing = seen[doi_lower]
                if result.source == "pubmed":
                    seen[doi_lower] = result
                elif result.open_access and not existing.open_access:
                    seen[doi_lower] = result

        results = list(seen.values())

        # Sort: open access first, then by date (newest first)
        def sort_key(r):
            oa_score = (0 if r.open_access else 1)
            date_score = r.pub_date or "0000-00-00"
            return (oa_score, -1 * int(date_score[:4]))  # Negative year for reverse sort

        results.sort(key=sort_key)

        summary = {
            "query": query,
            "total_unique": len(results),
            "pubmed_count": len(pubmed_results),
            "crossref_count": len(crossref_results),
            "open_access_count": sum(1 for r in results if r.open_access),
            "search_date": datetime.now().isoformat(),
        }

        logger.info(
            f"Search complete: {len(results)} unique DOIs "
            f"({sum(1 for r in results if r.open_access)} open access)"
        )

        return {
            "results": results,
            "summary": summary,
        }


def search_and_save(
    query: str,
    output_json: str,
    max_results: int = 100,
    min_year: Optional[int] = None,
) -> dict:
    """
    Convenience function: search and save results to JSON.

    Args:
        query: Search term
        output_json: Path to save results
        max_results: Max articles per source
        min_year: Year filter

    Returns:
        Results dict (same as ArticleSearcher.search())
    """
    searcher = ArticleSearcher()
    results = searcher.search(query, max_results, min_year)

    # Save to JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": results["summary"],
                "results": [r.to_dict() for r in results["results"]],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    logger.info(f"Results saved to {output_json}")

    return results
