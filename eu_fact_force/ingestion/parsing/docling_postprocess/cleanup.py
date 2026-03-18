"""Rendered-text cleanup helpers for Docling output."""

from __future__ import annotations

import re

from .constants import DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS


def _collect_snippet_sets(
    dropped_blocks: list[dict[str, object]],
) -> tuple[set[str], set[str]]:
    """
    Split dropped snippets into removal buckets.

    Returns:
    - small_box_line_snippets: snippets from tiny boxes, line-removal only
    - non_small_line_snippets: non-small snippets, line-removal only
    """
    small_box_line_snippets: set[str] = set()
    non_small_line_snippets: set[str] = set()

    for block in dropped_blocks:
        snippet_raw = block.get("text")
        if not isinstance(snippet_raw, str):
            continue
        snippet = snippet_raw.strip()
        if not snippet:
            continue

        is_small_box = bool(block.get("is_small_box", False))
        if is_small_box:
            if len(snippet) >= DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS:
                small_box_line_snippets.add(snippet)
            continue

        if len(snippet) >= DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS:
            non_small_line_snippets.add(snippet)

    return small_box_line_snippets, non_small_line_snippets


def _apply_line_based_removals(text: str, snippets: set[str]) -> str:
    """Remove snippets only when they match complete stripped lines."""
    if not snippets:
        return text
    kept_lines: list[str] = []
    for line in text.splitlines():
        if line.strip() in snippets:
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def remove_dropped_docling_snippets(
    rendered_text: str,
    dropped_blocks: list[dict[str, object]],
) -> str:
    """
    Remove text snippets from blocks flagged as ghost OCR.

    Strategy:
    - Remove dropped snippets only when they match full stripped lines.
    - Do not apply global in-text replacement.
    - Collapse excessive blank lines after removals.
    """
    (
        small_box_line_snippets,
        non_small_line_snippets,
    ) = _collect_snippet_sets(dropped_blocks=dropped_blocks)

    cleaned = rendered_text
    line_snippets = small_box_line_snippets.union(non_small_line_snippets)
    cleaned = _apply_line_based_removals(cleaned, line_snippets)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
