"""
Shared utility functions for quality scoring.

Provides fuzzy matching, text normalization, and helper functions
used across all scoring modules.
"""

import re
from difflib import SequenceMatcher

# =========================
# SHARED CONSTANTS
# =========================

# Status values returned by scoring functions
FOUND = "found"
NOT_FOUND = "not_found"
NOT_APPLICABLE = "n/a"

# Fuzzy matching
DEFAULT_FUZZY_THRESHOLD = 0.75
EARLY_EXIT_RATIO = 0.95
SLIDING_WINDOW_STEP_DIVISOR = 4

# Text search regions
METADATA_SEARCH_CHARS = 5000

# Sentence splitting
MIN_SENTENCE_CHARS = 30

# Sentence matching
LENGTH_MISMATCH_RATIO = 0.5

# References section
REFERENCES_SEARCH_START_FRACTION = 0.40


# =========================
# FUZZY MATCHING
# =========================

def contains_fuzzy(
    haystack: str,
    needle: str,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> tuple[bool, float]:
    """
    Check whether *needle* appears (possibly with minor OCR/parsing noise)
    somewhere in *haystack*.  Returns (found, best_ratio).
    Uses a sliding-window approach for short needles.
    """
    needle_lower = needle.lower()
    haystack_lower = haystack.lower()

    if needle_lower in haystack_lower:
        return True, 1.0

    window = len(needle_lower)
    best = 0.0
    step = max(1, window // SLIDING_WINDOW_STEP_DIVISOR)
    for i in range(0, len(haystack_lower) - window + 1, step):
        chunk = haystack_lower[i : i + window]
        ratio = SequenceMatcher(None, needle_lower, chunk).ratio()
        if ratio > best:
            best = ratio
        if best >= EARLY_EXIT_RATIO:
            break

    return best >= threshold, round(best, 3)


# =========================
# TEXT NORMALIZATION
# =========================

def normalize_for_dedup(text: str) -> str:
    """Collapse whitespace, lowercase, digits->#  for dedup comparisons."""
    t = re.sub(r"\s+", " ", text).strip().lower()
    t = re.sub(r"\d+", "#", t)
    return t


def normalize_for_similarity(text: str) -> str:
    """
    Normalize text for similarity comparison:
      - Remove markdown heading markers (# ## ###)
      - Remove [Figure N: ...] placeholders (ground truth markers)
      - Strip superscript citation numbers (unicode superscripts)
      - Collapse whitespace
      - Lowercase
    """
    t = re.sub(r"\[Figure\s+\d+[^]]*\]", "", text)
    t = re.sub(r"^#{1,4}\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+", "", t)
    t = re.sub(r"[⁰-⁹–,]+", "", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def strip_references_section(text: str) -> str:
    """
    Remove the references/bibliography section from the end of a text.
    This prevents easy-to-parse reference lists from inflating scores.

    Searches from 40% into the text onwards (references are at the end).
    """
    cutoff = int(len(text) * REFERENCES_SEARCH_START_FRACTION)
    lower = text.lower()
    for marker in ["\nreferences\n", "\n# references",
                   "\nbibliography\n", "\n# bibliography"]:
        pos = lower.rfind(marker, cutoff)
        if pos >= 0:
            return text[:pos].strip()
    return text


# =========================
# SENTENCE UTILITIES
# =========================

def split_sentences(text: str) -> list[str]:
    """
    Split normalized text into sentences.
    Returns sentences with length >= MIN_SENTENCE_CHARS (skip short fragments).
    """
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.strip()) >= MIN_SENTENCE_CHARS]


def best_match_ratio(
    needle: str,
    haystack_sentences: list[str],
    haystack_set: set[str],
) -> float:
    """Find the best SequenceMatcher ratio for *needle* among *haystack_sentences*."""
    if needle in haystack_set:
        return 1.0
    best = 0.0
    for hs in haystack_sentences:
        if abs(len(needle) - len(hs)) > len(needle) * LENGTH_MISMATCH_RATIO:
            continue
        ratio = SequenceMatcher(None, needle, hs).ratio()
        if ratio > best:
            best = ratio
        if best >= EARLY_EXIT_RATIO:
            break
    return best
