"""
Content presence and structural quality scoring.

Uses ground_truth.json annotations to evaluate:
  - Content presence (title, authors, DOI, abstract, references, key_passage)
  - Structural quality (fragmentation, section order, duplicates)
  - Continuity passages (text spanning page/column breaks)
"""

import re
from collections import Counter

from .utils import (
    contains_fuzzy, normalize_for_dedup,
    FOUND, NOT_FOUND, NOT_APPLICABLE, METADATA_SEARCH_CHARS,
)

# =========================
# CONSTANTS
# =========================

# Fuzzy matching threshold for content presence checks
CONTENT_FUZZY_THRESHOLD = 0.70

# Fragmentation detection
ORPHAN_LINE_MAX_CHARS = 40
MIN_HYPHENATED_LINE_CHARS = 5
BLANK_LIKE_MAX_CHARS = 3

# Duplicate content detection
MIN_PARAGRAPH_CHARS = 50

# Structural quality weights and worst-case thresholds
WEIGHT_FRAGMENTATION = 0.50
WEIGHT_SECTION_ORDER = 0.30
WEIGHT_DUPLICATES = 0.20
WORST_FRAGMENTATION_RATIO = 0.40
WORST_DUPLICATE_RATIO = 0.20

# Section order requires at least this many matched positions
MIN_SECTION_POSITIONS = 2


# =========================
# CONTENT-PRESENCE SCORING
# =========================

def score_title(full_text: str, expected_title: str) -> tuple[str, float]:
    """Check if expected title appears in the extracted text."""
    found, ratio = contains_fuzzy(full_text, expected_title, threshold=CONTENT_FUZZY_THRESHOLD)
    return (FOUND if found else NOT_FOUND), ratio


def score_authors(full_text: str, expected_authors: list[str]) -> tuple[str, float]:
    """Check if at least one author name appears in the extracted text."""
    snippet = full_text[:METADATA_SEARCH_CHARS]
    best_ratio = 0.0
    any_found = False
    for author in expected_authors:
        found, ratio = contains_fuzzy(snippet, author, threshold=CONTENT_FUZZY_THRESHOLD)
        best_ratio = max(best_ratio, ratio)
        if found:
            any_found = True
    return (FOUND if any_found else NOT_FOUND), best_ratio


def score_doi(full_text: str, expected_doi: str | None) -> str:
    """Check if the expected DOI appears in the extracted text."""
    if expected_doi is None:
        return NOT_APPLICABLE
    return FOUND if expected_doi in full_text else NOT_FOUND


def score_abstract(full_text: str, expected_first_sentence: str | None) -> tuple[str, float]:
    """Check if the abstract's first sentence appears in the text."""
    if expected_first_sentence is None:
        return NOT_APPLICABLE, 0.0
    found, ratio = contains_fuzzy(full_text, expected_first_sentence, threshold=CONTENT_FUZZY_THRESHOLD)
    return (FOUND if found else NOT_FOUND), ratio


def score_references(full_text: str) -> str:
    """Check if a references section is detectable."""
    if re.search(r"\breferences\b", full_text, re.IGNORECASE):
        return FOUND
    if re.search(r"\bbibliography\b", full_text, re.IGNORECASE):
        return FOUND
    return NOT_FOUND


def score_key_passage(full_text: str, expected_passage: str) -> tuple[str, float]:
    """Fuzzy-match the key passage against the full extracted text."""
    found, ratio = contains_fuzzy(full_text, expected_passage, threshold=CONTENT_FUZZY_THRESHOLD)
    return (FOUND if found else NOT_FOUND), ratio


# =========================
# STRUCTURAL QUALITY METRICS
# =========================

def score_fragmentation(full_text: str) -> float:
    """
    Measure text fragmentation from multi-column layout damage:
      - Lines ending with a hyphen followed by a word continuation on the next line
      - Orphan lines: very short non-blank lines that are not headings or list items

    Returns fragmentation_ratio (0.0 = clean, higher = more fragmented).
    """
    lines = full_text.splitlines()
    total = len(lines)
    if total == 0:
        return 0.0

    frag_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Hyphenated line break: line ends with letter-hyphen, next line starts lowercase
        if (
            stripped.endswith("-")
            and len(stripped) > MIN_HYPHENATED_LINE_CHARS
            and i + 1 < total
            and lines[i + 1].strip()
            and lines[i + 1].strip()[0].islower()
        ):
            frag_count += 1
            continue

        # Orphan line: short, not a heading/list/blank
        if len(stripped) < ORPHAN_LINE_MAX_CHARS:
            is_heading = stripped.startswith("#")
            is_list = bool(re.match(r"^[-*•]\s|^\d+[\.\)]\s", stripped))
            is_blank_like = len(stripped) < BLANK_LIKE_MAX_CHARS
            if not is_heading and not is_list and not is_blank_like:
                frag_count += 1

    non_blank = sum(1 for line in lines if line.strip())
    return round(frag_count / max(1, non_blank), 4)


def score_section_order(full_text: str, sections_in_order: list[str] | None) -> float | None:
    """
    Check whether markdown headings appear in the expected order.

    Only meaningful for text containing markdown headings.  Returns None
    if the text has no headings or the ground truth has too few sections.

    Returns a score between 0.0 (completely wrong) and 1.0 (perfect order),
    or None if not applicable.
    """
    if not sections_in_order or len(sections_in_order) < MIN_SECTION_POSITIONS:
        return None

    heading_pattern = re.compile(r"^#{1,3}\s+(.+)", re.MULTILINE)
    headings_found = [m.group(1).strip().lower() for m in heading_pattern.finditer(full_text)]

    if not headings_found:
        return None

    expected_lower = [s.lower() for s in sections_in_order]
    positions = []
    for expected in expected_lower:
        for idx, found_heading in enumerate(headings_found):
            if expected in found_heading or found_heading in expected:
                positions.append(idx)
                break

    if len(positions) < MIN_SECTION_POSITIONS:
        return None

    # Count pairs in correct relative order (Kendall-style concordance)
    correct = 0
    total_pairs = 0
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            total_pairs += 1
            if positions[i] < positions[j]:
                correct += 1

    return round(correct / total_pairs, 4) if total_pairs else None


def score_duplicate_content(full_text: str) -> float:
    """
    Detect near-duplicate paragraphs (exact normalised match, >= MIN_PARAGRAPH_CHARS each).

    Returns duplicate_ratio: fraction of paragraphs that are duplicates.
    0.0 = no duplicates, higher = more redundancy.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]
    paragraphs = [p for p in paragraphs if len(p) >= MIN_PARAGRAPH_CHARS]

    if len(paragraphs) < 2:
        return 0.0

    normed = [normalize_for_dedup(p) for p in paragraphs]
    counts: Counter = Counter(normed)

    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)

    return round(duplicate_count / len(paragraphs), 4)


def compute_structural_quality(
    fragmentation: float,
    section_order: float | None,
    duplicate_ratio: float,
) -> float:
    """
    Combine structural metrics into a single 0-100 score.

    Weights (among applicable components):
      - fragmentation: 50%  (0 frag -> 100, ratio >= 0.40 -> 0)
      - section_order: 30%  (1.0 -> 100, 0.0 -> 0; if n/a, weight redistributed)
      - duplicates:    20%  (0 dupes -> 100, ratio >= 0.20 -> 0)
    """
    def _ratio_to_score(value: float, worst: float) -> float:
        return max(0.0, min(100.0, (1.0 - value / worst) * 100.0))

    s_frag = _ratio_to_score(fragmentation, WORST_FRAGMENTATION_RATIO)
    s_dupes = _ratio_to_score(duplicate_ratio, WORST_DUPLICATE_RATIO)

    if section_order is not None:
        s_order = section_order * 100.0
        weighted = (
            s_frag * WEIGHT_FRAGMENTATION
            + s_order * WEIGHT_SECTION_ORDER
            + s_dupes * WEIGHT_DUPLICATES
        )
    else:
        # Redistribute section_order weight proportionally to frag and dupes
        total = WEIGHT_FRAGMENTATION + WEIGHT_DUPLICATES
        weighted = (
            s_frag * (WEIGHT_FRAGMENTATION / total)
            + s_dupes * (WEIGHT_DUPLICATES / total)
        )

    return round(weighted, 1)


# =========================
# CONTINUITY PASSAGE SCORING
# =========================

def score_continuity_passages(
    full_text: str,
    passages: list[dict] | None,
) -> tuple[int, int, float]:
    """
    Check whether continuity passages (text spanning page/column breaks)
    appear as contiguous text in the extract.

    Returns (found_count, total_count, avg_ratio).
    """
    if not passages:
        return 0, 0, 0.0

    found = 0
    ratios = []
    for p in passages:
        text = p["text"]
        ok, ratio = contains_fuzzy(full_text, text, threshold=CONTENT_FUZZY_THRESHOLD)
        ratios.append(ratio)
        if ok:
            found += 1

    avg = round(sum(ratios) / len(ratios), 3) if ratios else 0.0
    return found, len(passages), avg
