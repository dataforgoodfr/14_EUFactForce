"""Metadata detection helpers for benchmark records."""

from __future__ import annotations

import re

# Heuristic thresholds for metadata detection
MIN_TITLE_LENGTH = 10
MAX_TITLE_LENGTH = 300
# Limit title detection to first front-matter lines to avoid body-text matches.
TITLE_SCAN_LINES = 10
# Limit author detection scan to early text where author credits usually appear.
AUTHOR_CHUNK_CHARS = 2000


def detect_doi(text: str) -> str:
    """Search for a DOI pattern (e.g. 10.1234/...) anywhere in extracted text."""
    return "found" if re.search(r"10\.\d{4,}/\S+", text) else "not_found"


def detect_abstract(text: str) -> str:
    """Check whether the word 'Abstract' appears as a section heading."""
    return "found" if re.search(r"\babstract\b", text, re.IGNORECASE) else "not_found"


def detect_references(text: str) -> str:
    """Check whether a 'References' section exists (typically at the end)."""
    return "found" if re.search(r"\breferences\b", text, re.IGNORECASE) else "not_found"


def detect_title(first_chunk: str) -> str:
    """Heuristic: a title-like line should appear in the first few lines."""
    for line in first_chunk.strip().splitlines()[:TITLE_SCAN_LINES]:
        stripped = line.strip()
        if MIN_TITLE_LENGTH < len(stripped) < MAX_TITLE_LENGTH:
            return "found"
    return "not_found"


def detect_authors(first_chunk: str) -> str:
    """Heuristic: look for name-like patterns or 'Author(s):' in the first N chars."""
    snippet = first_chunk[:AUTHOR_CHUNK_CHARS]
    patterns = [
        r"[A-Z][a-z]+\s+[A-Z][a-z]+",  # Firstname Lastname
        r"(?:authors?|by)\s*:",  # Explicit label for authors
        r"[A-Z]\.\s*[A-Z][a-z]+",  # J. Smith
    ]
    for pat in patterns:
        if re.search(pat, snippet):
            return "found"
    return "not_found"


def compute_metadata_score(record: dict) -> int:
    """Count how many of the 5 metadata fields were detected."""
    fields = ["has_doi", "has_abstract", "has_references", "has_title", "has_authors"]
    return sum(1 for f in fields if record.get(f) == "found")

