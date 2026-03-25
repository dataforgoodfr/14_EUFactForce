"""Markdown normalization helpers for Docling output."""

from __future__ import annotations

import re

from .constants import DEMOTED_HEADER_LABELS


def normalize_markdown_headers_for_gt(markdown_text: str) -> str:
    """
    Normalize headings to level-1 to match GT editorial convention.

    For Docling hierarchical-postprocessed markdown, we also promote
    demoted front-matter labels (e.g., "Abstract") back to headings.
    """
    lines = markdown_text.splitlines()
    normalized: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            normalized.append(line)
            continue

        # Downgrade any markdown heading depth to level 1.
        m = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if m:
            normalized.append(f"# {m.group(1).strip()}")
            continue

        # Promote known demoted header labels to level 1 headings.
        if stripped.lower() in DEMOTED_HEADER_LABELS:
            normalized.append(f"# {stripped}")
            continue

        normalized.append(line)

    return "\n".join(normalized)
