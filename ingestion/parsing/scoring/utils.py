"""
Shared utility functions for quality scoring.

Provides fuzzy matching, text normalization, and helper functions
used across all scoring modules.
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

from text_cleaning import strip_legal_boilerplate_lines

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
FOOTNOTES_SEARCH_START_FRACTION = 0.50
TOC_SEARCH_END_FRACTION = 0.40
CITATION_NOISE_SEARCH_START_FRACTION = 0.60
REFERENCE_TEXT_EXTENSIONS = (".md", ".txt")


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
    tail = text[cutoff:]

    # Handle markdown headings (# .. ######) and plain section labels.
    refs_pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(references|bibliography|literature cited)\s*$"
    )
    match = refs_pattern.search(tail)
    if match:
        return text[: cutoff + match.start()].strip()

    # Fallback: implicit references detection for documents that do not carry
    # a clean "References" heading in extraction output.
    lines = text.splitlines()
    if len(lines) < 40:
        return text

    start_idx = int(len(lines) * REFERENCES_SEARCH_START_FRACTION)
    tail_lines = lines[start_idx:]
    if not tail_lines:
        return text

    ref_flags = [_looks_like_reference_line(line) for line in tail_lines]
    ref_count = sum(ref_flags)
    ref_ratio = ref_count / max(1, len(tail_lines))

    # Only activate when the latter part is clearly reference-heavy.
    if ref_count < 8 or ref_ratio < 0.12:
        return text

    kept_tail = [line for line, is_ref in zip(tail_lines, ref_flags) if not is_ref]
    cleaned_lines = lines[:start_idx] + kept_tail
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_footnotes_section(text: str) -> str:
    """
    Remove trailing footnotes/endnotes sections.

    We intentionally keep this conservative and focus on explicit section headers
    appearing in the latter part of the document.
    """
    cutoff = int(len(text) * FOOTNOTES_SEARCH_START_FRACTION)
    tail = text[cutoff:]

    footnotes_pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(footnotes|endnotes|notes)\s*$"
    )
    match = footnotes_pattern.search(tail)
    if match:
        return text[: cutoff + match.start()].strip()

    return text


def strip_legal_boilerplate(text: str) -> str:
    """
    Remove recurring legal/open-access boilerplate lines that are not body content.
    """
    return strip_legal_boilerplate_lines(text)


def find_reference_text_path(stem: str, gt_text_dir: Path) -> Path | None:
    """Find a ground-truth reference text file for the given document stem."""
    for ext in REFERENCE_TEXT_EXTENSIONS:
        candidate = gt_text_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def strip_trailing_citation_noise(text: str) -> str:
    """
    Trim citation-heavy trailing tail when no explicit references header exists.

    Trigger only if the tail has many URL/DOI/arXiv-like lines to stay conservative.
    """
    lines = text.splitlines()
    if len(lines) < 30:
        return text

    start_idx = int(len(lines) * CITATION_NOISE_SEARCH_START_FRACTION)
    tail = lines[start_idx:]
    if len(tail) < 12:
        return text

    citation_line = re.compile(r"(?i)(https?://|doi\.org|arxiv:|^10\.\d{4,}/)")
    first_noise_idx: int | None = None

    for i in range(0, len(tail) - 5):
        window = tail[i : i + 6]
        hit_count = sum(1 for ln in window if citation_line.search(ln.strip()))
        if hit_count >= 4:
            first_noise_idx = i
            break

    if first_noise_idx is None:
        return text

    cut_idx = start_idx + first_noise_idx
    if cut_idx <= int(len(lines) * 0.70):
        return text

    return "\n".join(lines[:cut_idx]).strip()


def _looks_like_toc_entry(line: str) -> bool:
    """
    Heuristic check for a Table-of-Contents entry line.

    Examples:
      - "1. Introduction ............ 3"
      - "References 27"
      - "Background\t12"
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Dot leaders are a strong signal of TOC rows.
    if re.search(r"\.{2,}", stripped):
        return True

    # Pipe-heavy rows are common in extracted TOC/table artifacts.
    if stripped.startswith("|") and stripped.count("|") >= 2:
        return True
    if re.match(r"^\|?\s*\d{1,3}\s*\|", stripped):
        return True

    # TOC entries often end with page numbers.
    if re.match(
        r"(?i)^\s*(?:[-*]\s*)?(?:\d+(?:\.\d+)*\s+)?[^\n]{2,140}?\s+\d{1,4}\s*$",
        stripped,
    ):
        return True

    return False


def _looks_like_reference_line(line: str) -> bool:
    """
    Heuristic check for bibliography/reference entry lines.
    """
    stripped = line.strip()
    if len(stripped) < 20:
        return False

    # Strong reference markers.
    if re.search(r"(?i)(https?://|doi\.org|arxiv:)", stripped):
        return True

    # Typical numbered reference format: "12. Author ... (2020)."
    if re.match(r"^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s+", stripped):
        if re.search(r"\b(19|20)\d{2}\b", stripped):
            return True
        if "," in stripped and len(stripped) > 45:
            return True

    # Common citation style with year in parentheses and journal-like punctuation.
    if re.search(r"\(\d{4}\)\.?$", stripped) and "," in stripped:
        return True

    return False


def strip_table_of_contents_section(text: str) -> str:
    """
    Remove an early Table-of-Contents block, if present.

    This is intentionally conservative:
    - only searches in the first TOC_SEARCH_END_FRACTION of the document
    - requires an explicit TOC heading
    - stops once content no longer looks like TOC rows
    """
    lines = text.splitlines()
    if not lines:
        return text

    search_end = max(1, int(len(lines) * TOC_SEARCH_END_FRACTION))
    toc_heading_pattern = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(table of contents|contents|toc)\s*$")
    body_heading_pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(abstract|introduction|executive summary|summary|background|review)\b"
    )

    toc_start: int | None = None
    for idx in range(search_end):
        if toc_heading_pattern.match(lines[idx].strip()):
            toc_start = idx
            break

    used_implicit_toc_fallback = False

    # Fallback for documents where TOC heading is missing but TOC rows are obvious.
    if toc_start is None:
        window = 10
        min_hits = 6
        best_start: int | None = None
        best_hits = 0
        for i in range(0, max(0, search_end - window)):
            chunk = lines[i : i + window]
            hits = sum(1 for ln in chunk if _looks_like_toc_entry(ln))
            if hits > best_hits:
                best_hits = hits
                best_start = i
        if best_start is not None and best_hits >= min_hits:
            toc_start = best_start
            used_implicit_toc_fallback = True
        else:
            return text

    toc_end = toc_start + 1
    consecutive_non_toc = 0
    max_scan = min(len(lines), toc_start + 250)
    non_toc_break_limit = 5 if used_implicit_toc_fallback else 2

    for idx in range(toc_start + 1, max_scan):
        line = lines[idx]
        stripped = line.strip()

        if not stripped:
            toc_end = idx + 1
            continue

        if _looks_like_toc_entry(stripped):
            toc_end = idx + 1
            consecutive_non_toc = 0
            continue

        if body_heading_pattern.match(stripped):
            break

        # Long narrative lines are unlikely to be TOC rows.
        if len(stripped) > 180:
            break

        consecutive_non_toc += 1
        if consecutive_non_toc >= non_toc_break_limit:
            break

        toc_end = idx + 1

    kept = lines[:toc_start] + lines[toc_end:]
    return "\n".join(kept).strip()


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
