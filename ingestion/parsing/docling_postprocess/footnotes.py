"""Footnote relocation helpers for Docling-rendered text."""

from __future__ import annotations

import re


def docling_snippet_variants(snippet: str) -> list[str]:
    """
    Generate safe text variants for matching Docling snippets in markdown output.

    Docling markdown can escape underscores (\\_) while label text may keep them
    unescaped (_), so we try both forms.
    """
    s = snippet.strip()
    if not s:
        return []
    variants = {s, s.replace("_", r"\_"), s.replace(r"\_", "_")}
    return sorted(variants, key=len, reverse=True)


def relocate_docling_labeled_footnotes(
    rendered_text: str,
    doc_dict: dict,
    result_type: str,
) -> str:
    """
    Use Docling block labels to move footnote text to a dedicated trailing section.
    """
    footnotes = [
        str(item.get("text", "")).strip()
        for item in doc_dict.get("texts", [])
        if str(item.get("label", "")).strip().lower() == "footnote"
        and str(item.get("text", "")).strip()
    ]
    if not footnotes:
        return rendered_text

    cleaned = rendered_text
    # Deduplicate and remove longest snippets first.
    uniq = sorted(set(footnotes), key=len, reverse=True)
    kept_footnotes: list[str] = []
    for snippet in uniq:
        removed = False
        for candidate in docling_snippet_variants(snippet):
            if candidate in cleaned:
                cleaned = cleaned.replace(candidate, "")
                removed = True
        if removed:
            kept_footnotes.append(snippet)

    if not kept_footnotes:
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    section_title = "# Footnotes" if result_type == "markdown" else "Footnotes"
    return f"{cleaned}\n\n{section_title}\n\n" + "\n\n".join(kept_footnotes)
