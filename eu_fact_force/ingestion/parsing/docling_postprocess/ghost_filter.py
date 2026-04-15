"""Ghost-text filtering helpers for Docling output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import fitz as PyMuPDF

from .constants import (
    DOCLING_PICTURE_OVERLAP_BLOCK_RATIO,
    DOCLING_PICTURE_OVERLAP_DROP_RATIO,
    DOCLING_PYMUPDF_MIN_SHARED_TOKENS,
    DOCLING_PYMUPDF_MIN_TOKEN_OVERLAP_RATIO,
    DOCLING_SMALL_BOX_MAX_AREA_RATIO,
)
from .geometry import (
    build_docling_picture_regions_by_page,
    docling_bbox_to_rect,
    rect_area_ratio,
    rect_overlap_ratio,
)


def rect_has_pdf_words(page: PyMuPDF.Page, rect: PyMuPDF.Rect, min_tokens: int = 1) -> bool:
    """Check whether a PDF rect contains real extractable word tokens."""
    if not is_usable_rect(rect):
        return False

    words = page.get_text("words", clip=rect)
    if not words:
        return False

    return has_min_meaningful_tokens(words, min_tokens=min_tokens)


def is_usable_rect(rect: PyMuPDF.Rect) -> bool:
    """Return whether a rectangle is non-empty and has positive dimensions."""
    return (not rect.is_empty) and rect.width > 0 and rect.height > 0


def has_min_meaningful_tokens(words: list, min_tokens: int) -> bool:
    """Check whether OCR words contain at least `min_tokens` alphanumeric tokens."""
    token_count = 0
    for word in words:
        token = str(word[4]).strip()
        # Require at least one alphanumeric to avoid punctuation-only artifacts.
        if token and re.search(r"[A-Za-z0-9]", token):
            token_count += 1
            if token_count >= min_tokens:
                return True
    return False


def tokenize_for_overlap(text: str) -> set[str]:
    """Tokenize text for lightweight agreement checks."""
    return {
        tok
        for tok in re.findall(r"[A-Za-z0-9]{2,}", text.lower())
        if len(tok) >= 2
    }


def bbox_word_tokens(page: PyMuPDF.Page, rect: PyMuPDF.Rect) -> set[str]:
    """Extract normalized word tokens from a PDF rectangle."""
    words = page.get_text("words", clip=rect)
    if not words:
        return set()
    raw = " ".join(str(w[4]) for w in words if str(w[4]).strip())
    return tokenize_for_overlap(raw)


def docling_text_agrees_with_pdf_words(
    docling_text: str,
    pdf_tokens: set[str],
    min_overlap_ratio: float = DOCLING_PYMUPDF_MIN_TOKEN_OVERLAP_RATIO,
    min_shared_tokens: int = DOCLING_PYMUPDF_MIN_SHARED_TOKENS,
) -> bool:
    """
    Check whether Docling text and PDF words in the same bbox reasonably agree.

    Prevents keeping gibberish Docling strings that happen to overlap valid text areas.
    """
    if not pdf_tokens:
        return False

    docling_tokens = tokenize_for_overlap(docling_text)
    if not docling_tokens:
        return False

    shared = docling_tokens.intersection(pdf_tokens)
    if len(shared) < min_shared_tokens:
        return False

    overlap_ratio = len(shared) / max(1, len(docling_tokens))
    return overlap_ratio >= min_overlap_ratio


def iter_scored_text_items(text_items: list[dict]) -> Iterator[tuple[str, str, list[dict]]]:
    """Yield non-empty text items as (text, label, provenance list)."""
    for item in text_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        label = str(item.get("label", "text")).strip().lower()
        provs = item.get("prov", [])
        yield text, label, provs


def is_inside_picture_region(
    *,
    label: str,
    page_no: int,
    rect: PyMuPDF.Rect,
    picture_regions: dict[int, list[PyMuPDF.Rect]],
) -> bool:
    """Return whether a non-caption block mostly overlaps a known picture region."""
    if label == "caption":
        return False
    pic_rects = picture_regions.get(page_no, [])
    return any(
        rect_overlap_ratio(rect, pic_rect) >= DOCLING_PICTURE_OVERLAP_DROP_RATIO
        for pic_rect in pic_rects
    )


def is_picture_dominated_block(
    *,
    label: str,
    prov_count: int,
    prov_inside_picture_count: int,
) -> bool:
    """Return whether most provenance boxes are inside picture regions."""
    if label == "caption" or prov_count <= 0:
        return False
    picture_ratio = prov_inside_picture_count / prov_count
    return picture_ratio >= DOCLING_PICTURE_OVERLAP_BLOCK_RATIO


def _parse_prov_page_index(prov: dict, page_count: int) -> tuple[int, int] | None:
    """Return (page_no, page_idx) when provenance points to a valid PDF page."""
    bbox = prov.get("bbox")
    if not bbox:
        return None
    page_no = int(prov.get("page_no", 1))
    page_idx = page_no - 1
    if page_idx < 0 or page_idx >= page_count:
        return None
    return page_no, page_idx


def _rect_and_area_ratio_from_prov(
    prov: dict, page: PyMuPDF.Page
) -> tuple[PyMuPDF.Rect, float]:
    """Build bbox rect and compute its area ratio against the page."""
    rect = docling_bbox_to_rect(prov["bbox"], page.rect.height)
    area_ratio = rect_area_ratio(rect, page.rect)
    return rect, area_ratio


def _prov_supports_keep(
    *,
    text: str,
    label: str,
    page_no: int,
    page: PyMuPDF.Page,
    rect: PyMuPDF.Rect,
    picture_regions: dict[int, list[PyMuPDF.Rect]],
) -> tuple[bool, bool]:
    """
    Evaluate one provenance box contribution.

    Returns:
    - is_inside_picture: whether this provenance is picture-overlapped
    - supports_keep: whether this provenance confirms the text block should be kept
    """
    if is_inside_picture_region(
        label=label,
        page_no=page_no,
        rect=rect,
        picture_regions=picture_regions,
    ):
        return True, False

    if not rect_has_pdf_words(page, rect):
        return False, False

    pdf_tokens = bbox_word_tokens(page, rect)
    return False, docling_text_agrees_with_pdf_words(text, pdf_tokens)


def evaluate_text_block_keep(
    *,
    text: str,
    label: str,
    provs: list[dict],
    pdf: PyMuPDF.Document,
    picture_regions: dict[int, list[PyMuPDF.Rect]],
) -> tuple[bool, float]:
    """Evaluate whether a text block should be kept and return max bbox area ratio."""
    # Keep blocks without provenance to avoid accidental data loss.
    if not provs:
        return True, 0.0

    keep = False
    prov_count = 0
    prov_inside_picture_count = 0
    max_bbox_area_ratio = 0.0

    for prov in provs:
        parsed_page = _parse_prov_page_index(prov=prov, page_count=len(pdf))
        if parsed_page is None:
            continue
        page_no, page_idx = parsed_page
        prov_count += 1

        page = pdf[page_idx]
        rect, area_ratio = _rect_and_area_ratio_from_prov(prov=prov, page=page)
        max_bbox_area_ratio = max(max_bbox_area_ratio, area_ratio)

        is_inside_picture, supports_keep = _prov_supports_keep(
            text=text,
            label=label,
            page_no=page_no,
            page=page,
            rect=rect,
            picture_regions=picture_regions,
        )
        if is_inside_picture:
            prov_inside_picture_count += 1
            continue
        if supports_keep:
            keep = True
            break

    # If most provenance boxes are inside picture regions, treat as image OCR.
    if is_picture_dominated_block(
        label=label,
        prov_count=prov_count,
        prov_inside_picture_count=prov_inside_picture_count,
    ):
        keep = False

    return keep, max_bbox_area_ratio


def collect_docling_ghost_text_blocks(
    file_path: Path,
    doc_dict: dict,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """
    Identify Docling text blocks whose bboxes map to no real PDF words.

    This mitigates ghost Docling text regions in highly stylized PDFs.
    """
    text_items = doc_dict.get("texts", [])
    dropped_blocks: list[dict[str, object]] = []
    dropped = 0
    considered = 0

    pdf = PyMuPDF.open(str(file_path))
    try:
        picture_regions = build_docling_picture_regions_by_page(doc_dict, pdf)
        for text, label, provs in iter_scored_text_items(text_items):
            considered += 1
            keep, max_bbox_area_ratio = evaluate_text_block_keep(
                text=text,
                label=label,
                provs=provs,
                pdf=pdf,
                picture_regions=picture_regions,
            )
            if keep:
                continue

            dropped_blocks.append(
                {
                    "text": text,
                    "is_small_box": max_bbox_area_ratio <= DOCLING_SMALL_BOX_MAX_AREA_RATIO,
                }
            )
            dropped += 1
    finally:
        pdf.close()

    stats = {
        "considered_text_blocks": considered,
        "dropped_text_blocks": dropped,
    }
    return dropped_blocks, stats
