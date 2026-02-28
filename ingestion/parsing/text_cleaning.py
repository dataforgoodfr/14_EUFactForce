"""
Text post-processing for parsed PDF output.

Cleans up common extraction artifacts (encoding issues, hyphenation,
repeated lines) in a parser-agnostic way.

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


def postprocess_text(text: str, doc_type: str | None = None) -> str:
    """
    Clean up common extraction artifacts in parser output.

    Applies the following fixes (in order):
      1. Fix ∞ used as letter 'a' (LlamaParse-specific artifact)
      2. Decode HTML hex entities (&#x26; → &)
      3. Decode HTML named entities (&amp; → &)
      4. Rejoin hyphenated line breaks (misinforma-\\ntion → misinformation)
      5. Remove markdown/html layout placeholders
      6. Rejoin paragraphs interrupted by figure/table blocks
      7. Scientific-paper specific cleanup (optional)
      8. Remove residual repeated lines

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

    # --- 5. Remove markdown/html layout placeholders ---
    t = re.sub(r"(?im)^\s*<!--\s*image\s*-->\s*$", "", t)
    t = re.sub(r"(?im)^\s*<!--.*?-->\s*$", "", t)

    # --- 6. Rejoin paragraphs split by inline layout artifacts ---
    t = _rejoin_interrupted_paragraphs(t)

    # --- 7. Scientific-paper specific cleanup ---
    if doc_type == "scientific_paper":
        t = _clean_scientific_paper_noise(t)

    # --- 8. Remove repeated lines (residual noise) ---
    t = remove_repeated_lines(t)

    return t


# =========================
# PARAGRAPH STITCHING
# =========================

def _split_blocks(text: str) -> list[str]:
    """Split text into paragraph-like blocks using blank lines."""
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _is_heading_block(block: str) -> bool:
    first = block.splitlines()[0].strip()
    return first.startswith("#")


def _is_table_block(block: str) -> bool:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return False
    if all(ln.startswith("|") for ln in lines):
        return True
    if re.match(r"^Table\s+\d+\b", lines[0], re.IGNORECASE):
        return True
    return False


def _is_layout_artifact_block(block: str) -> bool:
    if block.startswith("<!--") and block.endswith("-->"):
        return True
    first = block.splitlines()[0].strip()
    if first in {"ScienceDirect", "Review"}:
        return True
    return False


def _is_interruption_block(block: str) -> bool:
    return _is_heading_block(block) or _is_table_block(block) or _is_layout_artifact_block(block)


def _starts_with_lowercase(block: str) -> bool:
    s = block.lstrip()
    return bool(s) and s[0].islower()


def _looks_like_body_paragraph(block: str) -> bool:
    if _is_interruption_block(block):
        return False
    # Exclude list-style reference entries and bullet blocks.
    if re.match(r"^[-*]\s+", block):
        return False
    if re.match(r"^\d+\.\s", block):
        return False
    return len(block.split()) >= 12


def _ends_as_incomplete_sentence(block: str) -> bool:
    s = block.rstrip()
    if not s:
        return False
    # Treat terminal punctuation as complete sentence boundary.
    return s[-1] not in ".!?;:)”’]"


def _rejoin_interrupted_paragraphs(text: str, max_gap_blocks: int = 8) -> str:
    """
    Rejoin body paragraphs split by non-body blocks (figures/tables/headings).

    Example:
      [body ending with "... this discomfort is"]
      [layout blocks: image/table/heading]
      [body starting with "associated with ..."]
    becomes a single continuous body paragraph.
    """
    blocks = _split_blocks(text)
    consumed = [False] * len(blocks)

    for i, block in enumerate(blocks):
        if consumed[i]:
            continue
        if not _looks_like_body_paragraph(block):
            continue
        if not _ends_as_incomplete_sentence(block):
            continue

        # Seek the next plausible continuation block after interruptions.
        found_j: int | None = None
        for j in range(i + 1, min(len(blocks), i + 1 + max_gap_blocks)):
            if consumed[j]:
                continue
            candidate = blocks[j]
            if _is_interruption_block(candidate):
                continue
            if _looks_like_body_paragraph(candidate) and _starts_with_lowercase(candidate):
                found_j = j
                break
            if _looks_like_body_paragraph(candidate):
                break
            continue

        if found_j is None:
            continue

        blocks[i] = f"{blocks[i].rstrip()} {blocks[found_j].lstrip()}"
        consumed[found_j] = True

    merged_blocks = [b for idx, b in enumerate(blocks) if not consumed[idx]]
    return "\n\n".join(merged_blocks)


def _clean_scientific_paper_noise(text: str) -> str:
    """
    Remove recurring scientific-paper boilerplate and parser artifacts.
    """
    t = text

    # Common OCR/control-word artifacts seen in article headers.
    t = re.sub(r"(?i)\bhairspace\b", " ", t)

    # Remove common legal/open-access boilerplate blocks.
    legal_patterns = [
        r"(?im)^\s*open access this article is licensed under a creative commons.*$",
        r"(?im)^\s*to view a copy of this licence visit .*creativecommons\.org.*$",
        r"(?im)^\s*if material is not included in the article.?s creative commons licence.*$",
        r"(?im)^\s*the creative commons public domain dedication waiver.*$",
        r"(?im)^\s*©\s*the author\(s\)\s*\d{4}.*$",
    ]
    for pattern in legal_patterns:
        t = re.sub(pattern, "", t)

    # Remove submission metadata lines that are rarely part of body GT.
    t = re.sub(r"(?im)^\s*received:\s*.+?/+\s*accepted:\s*.+$", "", t)

    # Remove correspondence footers often injected in publisher templates.
    t = re.sub(r"(?im)^\s*\*?\s*correspondence:\s*.*$", "", t)

    # Normalize whitespace after removals.
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
