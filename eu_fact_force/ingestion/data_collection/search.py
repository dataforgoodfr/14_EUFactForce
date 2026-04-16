"""
Search for scientific articles on a given topic across PubMed and Crossref.

Supports keyword/topic search (e.g. "vaccine autism"), date filtering,
open-access preference, and DOI-level deduplication across sources.
"""

import logging
from dataclasses import dataclass, asdict
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    doi: str
    title: str
    authors: list[str]
    pub_year: Optional[int]
    journal: Optional[str]
    source: str           # "pubmed" | "crossref"
    open_access: Optional[bool] = None
    url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class PubMedSearcher:
    """Search PubMed via NCBI eUtils."""

    _SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    _SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    _BASE_PARAMS = {"tool": "eu-fact-force", "email": "bot@dataforgood.fr"}

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
    ) -> list[SearchResult]:
        if min_year:
            query = f"{query} AND {min_year}[PDAT]:3000[PDAT]"

        try:
            resp = requests.get(
                self._SEARCH_URL,
                params={**self._BASE_PARAMS, "db": "pubmed", "term": query,
                        "retmax": max_results, "retmode": "json", "sort": "relevance"},
                timeout=30,
            )
            resp.raise_for_status()
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                logger.info("pubmed.no_results query=%s", query[:60])
                return []
            logger.info("pubmed.ids_found count=%d", len(ids))

            resp = requests.get(
                self._SUMMARY_URL,
                params={**self._BASE_PARAMS, "db": "pubmed",
                        "id": ",".join(ids), "retmode": "json"},
                timeout=30,
            )
            resp.raise_for_status()

            results = []
            for uid, doc in resp.json().get("result", {}).items():
                if uid == "uids":
                    continue
                doi = next(
                    (a["value"] for a in doc.get("articleids", []) if a.get("idtype") == "doi"),
                    None,
                )
                if not doi:
                    continue
                pub_year = _parse_year(doc.get("pubdate", ""))
                results.append(SearchResult(
                    doi=doi,
                    title=doc.get("title", ""),
                    authors=[a.get("name", "") for a in doc.get("authors", [])],
                    pub_year=pub_year,
                    journal=doc.get("fulljournalname"),
                    source="pubmed",
                ))

            logger.info("pubmed.results count=%d", len(results))
            return results

        except Exception:
            logger.exception("pubmed.search_failed query=%s", query[:60])
            return []


class CrossrefSearcher:
    """Search Crossref works API."""

    _URL = "https://api.crossref.org/works"
    _HEADERS = {"User-Agent": "eu-fact-force (bot@dataforgood.fr)"}

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
    ) -> list[SearchResult]:
        try:
            params: dict = {
                "query": query,
                "rows": max_results,
                "select": "DOI,title,author,published-online,published-print,container-title",
            }
            if min_year:
                params["filter"] = f"from-pub-date:{min_year}-01-01"

            resp = requests.get(self._URL, params=params, headers=self._HEADERS, timeout=30)
            resp.raise_for_status()

            items = resp.json().get("message", {}).get("items", [])
            logger.info("crossref.results count=%d", len(items))

            results = []
            for item in items:
                doi = item.get("DOI")
                if not doi:
                    continue
                pub_year = _crossref_year(item)
                results.append(SearchResult(
                    doi=doi,
                    title=(item.get("title") or [""])[0],
                    authors=[
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in item.get("author", [])
                    ],
                    pub_year=pub_year,
                    journal=(item.get("container-title") or [""])[0],
                    source="crossref",
                    open_access=item.get("is-oa"),
                ))
            return results

        except Exception:
            logger.exception("crossref.search_failed query=%s", query[:60])
            return []


class ArticleSearcher:
    """Search PubMed + Crossref, deduplicate by DOI, sort open-access first."""

    def __init__(self) -> None:
        self._pubmed = PubMedSearcher()
        self._crossref = CrossrefSearcher()

    def search(
        self,
        query: str,
        max_results: int = 100,
        min_year: Optional[int] = None,
    ) -> list[SearchResult]:
        """Return deduplicated results sorted by open-access then newest-first."""
        pubmed = self._pubmed.search(query, max_results, min_year)
        crossref = self._crossref.search(query, max_results, min_year)

        # Deduplicate by normalised DOI; prefer PubMed when both sources match
        seen: dict[str, SearchResult] = {}
        for result in pubmed + crossref:
            key = result.doi.lower()
            if key not in seen:
                seen[key] = result
            elif result.source == "pubmed":
                # PubMed record takes precedence (richer metadata for biomedical)
                seen[key] = result

        results = list(seen.values())
        results.sort(key=_sort_key)

        logger.info(
            "search.complete unique=%d oa=%d pubmed=%d crossref=%d",
            len(results),
            sum(1 for r in results if r.open_access),
            len(pubmed),
            len(crossref),
        )
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_year(date_str: str) -> Optional[int]:
    """Extract a 4-digit year from a date string like '2023 Jan 15'."""
    for token in date_str.split():
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


def _crossref_year(item: dict) -> Optional[int]:
    """Extract publication year from a Crossref item (date-parts array)."""
    for key in ("published-online", "published-print", "published"):
        parts = item.get(key, {}).get("date-parts", [[]])
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def _sort_key(r: SearchResult) -> tuple:
    """Open-access first, then newest year first (None last)."""
    oa = 0 if r.open_access else 1
    year = -(r.pub_year or 0)
    return (oa, year)
