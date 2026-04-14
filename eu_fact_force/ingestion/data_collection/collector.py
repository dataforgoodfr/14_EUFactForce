import logging

from eu_fact_force.ingestion.data_collection.parsers import PARSERS

logger = logging.getLogger(__name__)


def _better(new, current):
    """Return True if new is a longer list or string than current."""
    if isinstance(new, (list, str)) and isinstance(new, type(current)):
        return len(new) > len(current)
    return False


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
        for field, value in result.items():
            if field == "found" or value is None:
                continue
            if field not in merged or _better(value, merged[field]):
                merged[field] = value
    return {"found": bool(sources), "sources": sources} | merged
