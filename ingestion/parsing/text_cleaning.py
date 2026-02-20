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


def postprocess_text(text: str) -> str:
    """
    Clean up common extraction artifacts in parser output.

    Applies the following fixes (in order):
      1. Fix ∞ used as letter 'a' (LlamaParse-specific artifact)
      2. Decode HTML hex entities (&#x26; → &)
      3. Decode HTML named entities (&amp; → &)
      4. Rejoin hyphenated line breaks (misinforma-\\ntion → misinformation)
      5. Remove residual repeated lines

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

    # --- 5. Remove repeated lines (residual noise) ---
    t = remove_repeated_lines(t)

    return t
