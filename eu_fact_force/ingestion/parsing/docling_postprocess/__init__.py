"""Docling-specific postprocessing helpers for parsing benchmark."""

from __future__ import annotations

from pathlib import Path

from .cleanup import remove_dropped_docling_snippets
from .footnotes import relocate_docling_labeled_footnotes
from .ghost_filter import collect_docling_ghost_text_blocks
from .markdown import normalize_markdown_headers_for_gt


def _export_docling_text(result, result_type: str) -> str:
    if result_type == "text":
        return result.document.export_to_text()
    if result_type == "markdown":
        return normalize_markdown_headers_for_gt(result.document.export_to_markdown())
    raise NotImplementedError(f"Unknown result_type: {result_type}")


def render_docling_output(
    file_path: Path,
    result,
    doc_dict: dict,
    result_type: str,
    validate_text_bboxes: bool = False,
) -> tuple[str, dict[str, int] | None]:
    """
    Render and post-process Docling output.

    Returns (full_text, bbox_stats_or_none).
    """
    full_text = _export_docling_text(result=result, result_type=result_type)
    stats: dict[str, int] | None = None

    if validate_text_bboxes:
        dropped_blocks, stats = collect_docling_ghost_text_blocks(
            file_path=file_path,
            doc_dict=doc_dict,
        )
        full_text = remove_dropped_docling_snippets(full_text, dropped_blocks)

    full_text = relocate_docling_labeled_footnotes(full_text, doc_dict, result_type)
    return full_text, stats

