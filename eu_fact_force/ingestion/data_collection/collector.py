import logging

from eu_fact_force.ingestion.data_collection.parsers import PARSERS

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


def _merge(merged: dict, update: dict) -> None:
    """Merge update into merged, keeping the most complete value per field."""
    for key, value in update.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            _merge(merged[key], value)
        elif _better(value, merged.get(key)):
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
    return {"found": bool(sources), "sources": sources} | merged
