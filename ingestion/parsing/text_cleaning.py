"""
Text post-processing for parsed PDF output.

Cleans up common extraction artifacts (encoding issues, hyphenation,
repeated lines) in a parser-agnostic way.
Normalization targets are aligned with the ground-truth editorial conventions
documented in ground_truth/README.md.

Used by benchmark.py to clean extracted text before saving.
"""

import html as _html_module
import re
from collections import Counter


def _normalize(text: str) -> str:
    """Collapse whitespace, lowercase, and replace digit sequences with #
    so that 'Page 685' and 'Page 686' are treated as the same block."""
    t = re.sub(r"\s+", " ", text).strip().lower()
    t = re.sub(r"\d+", "#", t)
    return t


# Hyphenated prefixes that should keep their hyphen when rejoining line breaks
_KEEP_HYPHEN_PREFIXES = frozenset({
    "self", "co", "re", "pre", "non", "anti", "counter", "cross",
    "over", "under", "inter", "intra", "multi", "post", "meta",
    "socio", "well", "long", "short", "high", "low",
})

# Generic thresholds for conservative tail dedup detection.
_TAIL_MAX_FRACTION = 0.18
_TAIL_MAX_LINES_FLOOR = 40
_OVERLAP_MIN_RATIO = 0.30
_HEAD_SAMPLE_MAX_LINES = 120


def _is_heading_like(line: str) -> bool:
    """Heuristic for short heading/title lines (not regular prose)."""
    s = line.strip()
    if not s:
        return False

    words = s.split()
    if len(words) > 12:
        return False

    # Markdown heading marker is already a strong signal.
    if s.startswith("#"):
        return True

    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(ch.isupper() for ch in letters) / len(letters)
    return uppercase_ratio >= 0.70


# =========================
# PUBLIC API
# =========================

def remove_repeated_lines(text: str, min_occurrences: int = 3) -> str:
    """
    Remove lines that appear >= *min_occurrences* times in *text*.

    This catches residual header/footer noise that survived PDF cropping,
    as well as watermark text (e.g. 'Downloaded from www.annualreviews.org').

    Returns the cleaned text.
    """
    lines = text.splitlines()
    normed = [_normalize(line) for line in lines]
    counts: Counter = Counter(normed)

    kept: list[str] = []
    for original, norm in zip(lines, normed):
        if not norm or counts[norm] < min_occurrences:
            kept.append(original)

    return "\n".join(kept)


def _relocate_explicit_footnotes_blocks(text: str) -> str:
    """
    Move explicit <footnotes>...</footnotes> blocks to the end of the document.

    This preserves content (instead of deleting it) while reducing mid-body
    disruptions that harm order-sensitive similarity scoring.
    """
    blocks: list[str] = []

    def _collect(match: re.Match) -> str:
        blocks.append(match.group(0).strip())
        return "\n"

    body = re.sub(r"(?is)<footnotes>.*?</footnotes>", _collect, text)
    if not blocks:
        return text

    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    relocated = "\n\n".join(blocks)
    return f"{body}\n\n{relocated}\n"


def _dedup_cover_tail(text: str) -> str:
    """
    Remove duplicated cover-like blocks when they reappear at the end.

    Conservative guards (generic, source-agnostic):
      - A duplicated anchor line must appear early and again in the last 15%.
      - The tail slice must be short enough to look like accidental repetition.
      - The tail must structurally overlap with heading-like lines seen near
        the beginning of the document.
    """
    lines = text.splitlines()
    if len(lines) < 20:
        return text

    # Index non-empty lines so we can find duplicate anchors robustly.
    non_empty = [(i, ln.strip()) for i, ln in enumerate(lines) if ln.strip()]
    if len(non_empty) < 10:
        return text

    first_zone_max = int(len(lines) * 0.30)
    last_zone_min = int(len(lines) * 0.85)

    # Candidate anchors: line-like titles that are likely stable across duplicates.
    candidates = [
        (i, s) for i, s in non_empty
        if 12 <= len(s) <= 120 and i <= first_zone_max and _is_heading_like(s)
    ]
    if not candidates:
        return text

    # Map of normalised line -> early index.
    early_pos: dict[str, int] = {}
    for i, s in candidates:
        key = re.sub(r"\s+", " ", s).lower()
        early_pos.setdefault(key, i)

    head_like_set = {
        re.sub(r"\s+", " ", ln.strip()).lower()
        for ln in lines[:_HEAD_SAMPLE_MAX_LINES]
        if ln.strip() and _is_heading_like(ln)
    }

    matched_cut_indices: list[int] = []
    for i, s in reversed(non_empty):
        if i < last_zone_min:
            break
        key = re.sub(r"\s+", " ", s).lower()
        if key in early_pos:
            # Ensure the tail looks like short accidental repetition.
            tail_lines = lines[i:]
            if len(tail_lines) > max(_TAIL_MAX_LINES_FLOOR, int(len(lines) * _TAIL_MAX_FRACTION)):
                continue
            tail_like_set = {
                re.sub(r"\s+", " ", ln.strip()).lower()
                for ln in tail_lines
                if ln.strip() and _is_heading_like(ln)
            }
            if not tail_like_set:
                continue
            overlap = len(tail_like_set & head_like_set) / len(tail_like_set)
            if overlap >= _OVERLAP_MIN_RATIO:
                matched_cut_indices.append(i)

    if not matched_cut_indices:
        return text

    # Keep the earliest valid cut within the duplicated tail block.
    cut_idx = min(matched_cut_indices)
    trimmed = "\n".join(lines[:cut_idx]).rstrip()
    return f"{trimmed}\n" if trimmed else text


def postprocess_text(text: str, profile: str = "default") -> str:
    """
    Clean up common extraction artifacts in parser output.

    Applies the following fixes (in order):
      1. Fix ∞ used as letter 'a' (LlamaParse-specific artifact)
      2. Decode HTML hex entities (&#x26; → &)
      3. Decode HTML named entities (&amp; → &)
      4. Rejoin hyphenated line breaks (misinforma-\\ntion → misinformation)
      5. Remove residual repeated lines

    Profiles:
      - default: safe parser-agnostic cleanup
      - policy_report: default + conservative tail dedup + footnotes relocation

    Returns the cleaned text.
    """
    t = text

    # --- 1. Fix ∞ replacing 'a' ---
    t = re.sub(r"(?<=[a-zA-Z])∞", "a", t)
    t = re.sub(r"∞(?=[a-zA-Z])", "a", t)

    # --- 2 & 3. Decode HTML entities ---
    t = re.sub(r"&#x[0-9a-fA-F]+;", lambda m: _html_module.unescape(m.group()), t)
    t = re.sub(r"&(?:amp|lt|gt|quot|apos);", lambda m: _html_module.unescape(m.group()), t)

    # --- 4. Rejoin hyphenated line breaks ---
    def _rejoin_hyphen(match: re.Match) -> str:
        before = match.group(1)
        after = match.group(2)
        if before.lower() in _KEEP_HYPHEN_PREFIXES:
            return f"{before}-{after}"
        return f"{before}{after}"

    t = re.sub(r"(\w+)-\s*\n\s*([a-z]\w*)", _rejoin_hyphen, t)

    # --- 4b. Rejoin spaced-hyphen line breaks (LlamaParse Markdown artifact) ---
    def _rejoin_spaced_hyphen(match: re.Match) -> str:
        before = match.group(1)
        after = match.group(2)
        if before.lower() in _KEEP_HYPHEN_PREFIXES:
            return f"{before}-{after}"
        return f"{before}{after}"

    t = re.sub(r"(\w+) - ([a-z]\w*)", _rejoin_spaced_hyphen, t)
    t = re.sub(r"(\w+) -\s*\n\s*([a-z]\w*)", _rejoin_spaced_hyphen, t)

    # --- 5. Optional profile-specific cleanup ---
    if profile == "policy_report":
        t = _dedup_cover_tail(t)
        t = _relocate_explicit_footnotes_blocks(t)
    elif profile != "default":
        raise ValueError(f"Unknown text cleaning profile: {profile}")

    # --- 6. Remove repeated lines (residual noise) ---
    # NOTE:
    # `_dedup_cover_tail()` and `_relocate_explicit_footnotes_blocks()` are
    # intentionally not applied by default because they can over-trim some
    # document layouts and reduce full-text fidelity. Keep them as opt-in
    # helpers for targeted document classes.
    t = remove_repeated_lines(t)

    return t
