"""
Text post-processing for parsed PDF output.

Cleans up common extraction artifacts (encoding issues, hyphenation,
repeated lines) in a parser-agnostic way.

Used by benchmark.py to clean extracted text before saving.
"""

import html as _html_module
import re
from collections import Counter


def normalize(text: str) -> str:
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

LEGAL_BOILERPLATE_PATTERNS: tuple[str, ...] = (
    r"(?im)^\s*open access this article is licensed under a creative commons.*$",
    r"(?im)^\s*to view a copy of this licence visit .*creativecommons\.org.*$",
    r"(?im)^\s*if material is not included in the article.?s creative commons licence.*$",
    r"(?im)^\s*the creative commons public domain dedication waiver.*$",
    r"(?im)^\s*received:\s*.+?/+\s*accepted:\s*.+$",
    r"(?im)^\s*\*?\s*correspondence:\s*.*$",
    r"(?im)^\s*©\s*the author\(s\)\s*\d{4}.*$",
)


def strip_legal_boilerplate_lines(text: str) -> str:
    """Remove recurring legal/open-access boilerplate lines."""
    cleaned = text
    for pattern in LEGAL_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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
    normed = [normalize(line) for line in lines]
    counts: Counter = Counter(normed)

    kept: list[str] = []
    for original, norm in zip(lines, normed):
        if not norm or counts[norm] < min_occurrences:
            kept.append(original)

    return "\n".join(kept)


def _fix_letter_artifacts(text: str) -> str:
    """Fix known character-substitution artifacts from some parser outputs."""
    fixed = re.sub(r"(?<=[a-zA-Z])∞", "a", text)
    fixed = re.sub(r"∞(?=[a-zA-Z])", "a", fixed)
    return fixed


def _decode_html_entities(text: str) -> str:
    """Decode HTML hex and common named entities in extracted text."""
    decoded = re.sub(r"&#x[0-9a-fA-F]+;", lambda m: _html_module.unescape(m.group()), text)
    decoded = re.sub(r"&(?:amp|lt|gt|quot|apos);", lambda m: _html_module.unescape(m.group()), decoded)
    return decoded


def postprocess_text(
    text: str,
    doc_type: str | None = None,
    indexing_cleanup: bool = False,
) -> str:
    """
    Clean up common extraction artifacts in parser output.

    Applies the following fixes (in order):
      1. Fix ∞ used as letter 'a' (parser artifact)
      2. Decode HTML hex entities (&#x26; → &)
      3. Decode HTML named entities (&amp; → &)
      4. Rejoin hyphenated line breaks (misinforma-\\ntion → misinformation)
      5. Remove markdown/html layout placeholders
      6. Rejoin paragraphs interrupted by figure/table blocks
      7. Doc-type specific cleanup (optional)
      8. Remove residual repeated lines
      9. Optional indexing-focused cleanup profile

    Returns the cleaned text.
    """
    t = text

    t = _fix_letter_artifacts(t)
    t = _decode_html_entities(t)

    def _rejoin_hyphen(match: re.Match) -> str:
        before = match.group(1)
        after = match.group(2)
        if before.lower() in _KEEP_HYPHEN_PREFIXES:
            return f"{before}-{after}"
        return f"{before}{after}"

    t = re.sub(r"(\w+)-\s*\n\s*([a-z]\w*)", _rejoin_hyphen, t)

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

    t = _rejoin_interrupted_paragraphs(t)

    # --- 7. Doc-type specific cleanup ---
    if doc_type == "scientific_paper":
        t = _clean_scientific_paper_noise(t)
    elif doc_type == "policy_advocacy":
        t = _clean_policy_advocacy_noise(t)

    t = remove_repeated_lines(t)

    if indexing_cleanup:
        t = _apply_indexing_cleanup(t)

    return t


def _apply_indexing_cleanup(text: str) -> str:
    """
    Apply conservative cleanup for retrieval-focused indexing output.
    """
    t = text
    lines = t.splitlines()
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        if _is_low_signal_indexing_line(stripped):
            continue

        cleaned.append(line)

    out = "\n".join(cleaned)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _is_low_signal_indexing_line(line: str) -> bool:
    """Heuristics for short noisy lines that hurt retrieval quality."""
    s = line.strip()

    if s in {"•", "Q"}:
        return True

    # Very short orphan tokens are usually OCR leftovers.
    if len(s) <= 3 and re.fullmatch(r"[A-Za-z0-9]+", s) and not s.isdigit():
        return True

    if s.startswith("#") or s.startswith("-"):
        return False

    # Mixed-script short lines are commonly OCR artifacts from image overlays.
    has_latin = bool(re.search(r"[A-Za-z]", s))
    has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", s))
    if len(s) <= 48 and has_latin and has_cyrillic:
        return True

    # Handle-like snippets (social tags/usernames) are low-signal for indexing.
    has_handle_like = bool(re.search(r"(^|[\s>])@\w+", s)) or "_" in s or "•" in s or ">" in s
    has_email = bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", s))
    has_sentence_punct = bool(re.search(r"[.!?;:]", s))
    word_count = len(s.split())
    if has_handle_like and not has_email and not has_sentence_punct and len(s) <= 120 and word_count <= 20:
        return True

    return False


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

    t = strip_legal_boilerplate_lines(t)

    # Normalize whitespace after removals.
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _clean_policy_advocacy_noise(text: str) -> str:
    """
    Remove common policy-advocacy extraction artifacts (logo-like OCR lines).
    """
    lines = text.splitlines()
    cleaned: list[str] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        # Keep explicit markdown structure/listing lines untouched.
        if stripped.startswith("#") or stripped.startswith("-"):
            cleaned.append(line)
            continue

        words = stripped.split()
        is_shortish = len(words) <= 3 and len(stripped) <= 28
        looks_upper_logo = bool(re.match(r"^[A-Z][A-Z0-9\-\s]{7,27}$", stripped))
        looks_garbled_code = bool(re.match(r"^[A-Z0-9\-]{3,}\s+[A-Z0-9\-]{2,}$", stripped))
        sentence_like = any(ch in stripped for ch in ".,;:!?")

        # Drop isolated short uppercase/code-like fragments (e.g., OCR logo residues).
        if is_shortish and not sentence_like and (looks_upper_logo or looks_garbled_code):
            continue

        # Drop isolated, short OCR-fragment lines that are unlikely to be semantic text.
        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_blank = idx == len(lines) - 1 or not lines[idx + 1].strip()
        isolated = prev_blank and next_blank

        words_clean = re.findall(r"[A-Za-z]{2,}", stripped)
        short_word_ratio = 0.0
        if words_clean:
            short_word_ratio = sum(1 for w in words_clean if len(w) <= 3) / len(words_clean)

        fragment_like = (
            isolated
            and len(stripped) <= 32
            and len(words_clean) <= 6
            and short_word_ratio >= 0.5
            and not any(ch.isdigit() for ch in stripped)
            and not stripped.startswith("(")
        )
        if fragment_like:
            continue

        cleaned.append(line)

    out = "\n".join(cleaned)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = _move_policy_inline_footnotes_to_end(out)
    return out.strip()


def _move_policy_inline_footnotes_to_end(text: str) -> str:
    """
    Move inline numbered citation/footnote paragraphs into a trailing section.

    This helps keep body flow cleaner and allows scoring to ignore the section
    via existing footnotes stripping.
    """
    working = text
    footnotes: list[str] = []

    # Merge any pre-existing footnotes section into our collector first.
    existing_heading = re.search(r"(?im)^\s*#\s*footnotes\s*$", working)
    if existing_heading:
        body_part = working[: existing_heading.start()].strip()
        foot_part = working[existing_heading.end() :].strip()
        if foot_part:
            footnotes.extend([b.strip() for b in re.split(r"\n\s*\n", foot_part) if b.strip()])
        working = body_part

    # Pass 1: line-level extraction for standalone citation lines.
    lines = working.splitlines()
    kept_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept_lines.append(line)
            continue

        if _looks_like_policy_footnote_line(stripped):
            # Handle mixed lines where citation tail is followed by new numbered body/ref text.
            split_match = re.search(r"\)\.\s+(\d{1,3}\s+[A-Z])", stripped)
            if split_match:
                foot = stripped[: split_match.start() + 2].strip()
                rest = stripped[split_match.start() + 3 :].strip()
                if foot:
                    footnotes.append(foot)
                if rest:
                    kept_lines.append(rest)
                continue

            footnotes.append(stripped)
            continue

        kept_lines.append(line)

    working = "\n".join(kept_lines).strip()

    # Pass 2: block-level extraction for longer reference-like paragraphs.
    blocks = [b.strip() for b in re.split(r"\n\s*\n", working) if b.strip()]
    kept_blocks: list[str] = []
    if blocks:
        start_scan = int(len(blocks) * 0.20)
        for idx, block in enumerate(blocks):
            if idx < start_scan:
                kept_blocks.append(block)
                continue
            if _looks_like_policy_footnote_block(block):
                footnotes.append(block)
            else:
                kept_blocks.append(block)

    if not footnotes:
        return "\n\n".join(kept_blocks).strip()

    # Deduplicate while preserving order.
    seen: set[str] = set()
    uniq_footnotes: list[str] = []
    for f in footnotes:
        if f in seen:
            continue
        seen.add(f)
        uniq_footnotes.append(f)

    return "\n\n".join(kept_blocks + ["# Footnotes"] + uniq_footnotes).strip()


def _looks_like_policy_footnote_block(block: str) -> bool:
    """
    Heuristic for policy-doc numbered citation/reference paragraphs.
    """
    first = block.splitlines()[0].strip()
    if not re.match(r"^\d{1,3}\s+", first):
        return False

    lower = block.lower()
    cues = (
        "available at:",
        "http://",
        "https://",
        "doi.org",
        "see:",
        "publication",
        "law",
        "regulation",
        "article ",
        "directive",
    )
    has_cue = any(c in lower for c in cues)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", block))

    # Require at least one citation cue plus year/date-like token.
    return has_cue and has_year


def _looks_like_policy_footnote_line(line: str) -> bool:
    """
    Heuristic for standalone citation lines in policy docs.
    """
    stripped = line.strip()
    if not re.match(r"^\d{1,3}\s+", stripped):
        return False

    lower = stripped.lower()
    has_url = bool(re.search(r"https?://|doi\.org", lower))
    has_available_at = "available at:" in lower
    has_cite_source = any(
        cue in lower
        for cue in (
            "regulation",
            "directive",
            "law ",
            "commission",
            "beuc",
            "ministry",
            "proposal",
        )
    )
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", stripped))

    return (has_url or has_available_at or has_cite_source) and has_year
