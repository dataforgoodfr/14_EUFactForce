import logging

from eu_fact_force.ingestion.data_collection.parsers import PARSERS

FIELD_ORDER = [
    "found",
    "sources",
    "title",
    "authors",
    "journal",
    "publication date",
    "status",
    "doi",
    "link",
    "document type",
    "document subtypes",
    "cited by count",
    "open access",
    "language",
    "abstract",
    "keywords",
    "cited articles",
]

logger = logging.getLogger(__name__)


def _better(new, current) -> bool:
    """Return True if new is more complete than current."""
    if current is None:
        return True
    if isinstance(new, list) and isinstance(current, list):
        return sum(v is not None for v in new) > sum(v is not None for v in current)
    if isinstance(new, str) and isinstance(current, str):
        return len(new) > len(current)
    return False


def _merge_authors(current: list, update: list) -> list:
    """Merge two author lists by name, preserving orcid associations."""
    orcid_by_name = {a["name"]: a["orcid"] for a in update if a.get("orcid")}
    base = current if len(current) >= len(update) else update
    return [{"name": a["name"], "orcid": orcid_by_name.get(a["name"]) or a.get("orcid")} for a in base]


def _is_pmc_link(url: str) -> bool:
    return "ncbi.nlm.nih.gov/pmc" in url


def _is_doi_link(url: str) -> bool:
    return "doi.org" in url


def _doi_count(refs: list) -> int:
    return sum(1 for r in refs if isinstance(r, str) and r.startswith("10."))


def _merge(merged: dict, update: dict) -> None:
    """Merge update into merged, keeping the most complete value per field, except for specific field :
    - for author : merge by name, preserving orcid associations.
    - for link : prefer non-PMC links.
    - for cited articles : prefer the one with more DOIs.
    """
    for key, value in update.items():
        if value is None:
            continue
        current = merged.get(key)
        if key == "authors" and isinstance(value, list) and isinstance(current, list):
            merged[key] = _merge_authors(current, value)
        elif key == "link" and isinstance(value, str) and isinstance(current, str):
            if _is_pmc_link(current) and not _is_pmc_link(value):
                merged[key] = value
            elif _is_doi_link(value) and not _is_doi_link(current):
                merged[key] = value
        elif key == "cited articles" and isinstance(value, list) and isinstance(current, list):
            if _doi_count(value) > _doi_count(current):
                merged[key] = value
        elif isinstance(value, dict) and isinstance(current, dict):
            _merge(merged[key], value)
        elif _better(value, current):
            merged[key] = value


def fetch_all(doi: str) -> dict:
    """Query all parsers for a DOI and merge results, keeping the most complete value per field."""
    merged = {}
    sources = []
    for parser in PARSERS:
        logger.info(f"Fetching metadata from {parser.__class__.__name__}...")
        try:
            result = parser.get_metadata(doi)
        except Exception as e:
            logger.warning(f"{parser.__class__.__name__} error: {e}")
            continue
        if not result.get("found"):
            continue
        sources.append(parser.__class__.__name__)
        _merge(merged, result)
    result = {"found": bool(sources), "sources": sources} | merged
    return {k: result.get(k) for k in FIELD_ORDER} | {k: v for k, v in result.items() if k not in FIELD_ORDER}
