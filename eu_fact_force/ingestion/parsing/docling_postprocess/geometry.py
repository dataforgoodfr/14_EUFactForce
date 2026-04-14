"""Geometry helpers for Docling/PyMuPDF bbox comparisons."""

from __future__ import annotations

import fitz as PyMuPDF


def docling_bbox_to_rect(bbox: dict, page_height: float) -> PyMuPDF.Rect:
    """Convert Docling bbox coordinates into PyMuPDF rect coordinates."""
    left = float(bbox["l"])
    right = float(bbox["r"])
    top_raw = float(bbox["t"])
    bottom_raw = float(bbox["b"])
    origin = str(bbox.get("coord_origin", "BOTTOMLEFT")).upper()

    if origin == "BOTTOMLEFT":
        y_top = page_height - max(top_raw, bottom_raw)
        y_bottom = page_height - min(top_raw, bottom_raw)
    else:
        y_top = min(top_raw, bottom_raw)
        y_bottom = max(top_raw, bottom_raw)

    return PyMuPDF.Rect(min(left, right), y_top, max(left, right), y_bottom)


def rect_overlap_ratio(inner: PyMuPDF.Rect, outer: PyMuPDF.Rect) -> float:
    """Return intersection area over inner rect area."""
    if inner.is_empty or outer.is_empty or inner.width <= 0 or inner.height <= 0:
        return 0.0
    inter = inner & outer
    if inter.is_empty:
        return 0.0
    return max(0.0, (inter.width * inter.height) / (inner.width * inner.height))


def rect_area_ratio(rect: PyMuPDF.Rect, page_rect: PyMuPDF.Rect) -> float:
    """Return rectangle area as ratio of full page area."""
    if (
        rect.is_empty
        or page_rect.is_empty
        or rect.width <= 0
        or rect.height <= 0
        or page_rect.width <= 0
        or page_rect.height <= 0
    ):
        return 0.0
    return (rect.width * rect.height) / (page_rect.width * page_rect.height)


def build_docling_picture_regions_by_page(doc_dict: dict, pdf: PyMuPDF.Document) -> dict[int, list[PyMuPDF.Rect]]:
    """
    Build picture regions by page from Docling dict.

    We treat text blocks mostly inside these regions as image OCR noise.
    """
    regions: dict[int, list[PyMuPDF.Rect]] = {}
    for item in doc_dict.get("pictures", []):
        for prov in item.get("prov", []):
            bbox = prov.get("bbox")
            if not bbox:
                continue
            page_no = int(prov.get("page_no", 1))
            page_idx = page_no - 1
            if page_idx < 0 or page_idx >= len(pdf):
                continue
            rect = docling_bbox_to_rect(bbox, pdf[page_idx].rect.height)
            regions.setdefault(page_no, []).append(rect)
    return regions
