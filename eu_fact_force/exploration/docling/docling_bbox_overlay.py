"""Overlay Docling element bounding boxes on a PDF and save an annotated copy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf as PyMuPDF


DEFAULT_OUTPUT_DIR = Path("results/annotated_pdf")

# RGB colors (0-1) by Docling element label.
LABEL_COLORS: dict[str, tuple[float, float, float]] = {
    "title": (0.85, 0.1, 0.1),
    "section_header": (1.0, 0.45, 0.05),
    "text": (0.1, 0.35, 0.9),
    "list_item": (0.4, 0.2, 0.8),
    "caption": (0.1, 0.7, 0.2),
    "footnote": (0.2, 0.65, 0.65),
    "page_header": (0.6, 0.6, 0.6),
    "page_footer": (0.45, 0.45, 0.45),
    "picture": (0.95, 0.75, 0.1),
    "table": (0.0, 0.6, 0.3),
}
DEFAULT_COLOR = (0.6, 0.1, 0.1)


def _extract_elements(doc_dict: dict) -> list[dict]:
    """Flatten relevant Docling blocks into drawable entries."""
    elements: list[dict] = []
    for section in ("texts", "pictures", "tables"):
        for item in doc_dict.get(section, []):
            label = item.get("label", section)
            for prov in item.get("prov", []):
                page_no = prov.get("page_no")
                bbox = prov.get("bbox")
                if not page_no or not bbox:
                    continue
                elements.append({"label": label, "page_no": page_no, "bbox": bbox})
    return elements


def _to_rect(bbox: dict, page_height: float) -> PyMuPDF.Rect:
    """Convert Docling bbox to a PyMuPDF Rect in top-left origin space."""
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

    x0 = min(left, right)
    x1 = max(left, right)
    return PyMuPDF.Rect(x0, y_top, x1, y_bottom)


def annotate_pdf(
    input_pdf: Path,
    output_pdf: Path,
    stroke_width: float = 0.8,
    docling_json: Path | None = None,
) -> tuple[int, int]:
    if docling_json is not None:
        doc_dict = json.loads(docling_json.read_text(encoding="utf-8"))
    else:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(input_pdf)
        doc_dict = result.document.export_to_dict()
    elements = _extract_elements(doc_dict)

    pdf = PyMuPDF.open(str(input_pdf))
    drawn = 0

    for element in elements:
        page_index = int(element["page_no"]) - 1
        if page_index < 0 or page_index >= len(pdf):
            continue
        page = pdf[page_index]
        rect = _to_rect(element["bbox"], page.rect.height)
        color = LABEL_COLORS.get(str(element["label"]), DEFAULT_COLOR)

        page.draw_rect(rect, color=color, width=stroke_width, overlay=True)
        page.insert_text(
            PyMuPDF.Point(rect.x0, max(8, rect.y0 - 2)),
            str(element["label"]),
            fontsize=6,
            color=color,
            overlay=True,
        )
        drawn += 1

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(str(output_pdf))
    pdf.close()
    return len(elements), drawn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an annotated PDF with Docling element bounding boxes."
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF file.")
    parser.add_argument(
        "--output-pdf",
        type=Path,
        default=None,
        help="Path for the annotated output PDF.",
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=0.8,
        help="Bounding box stroke width.",
    )
    parser.add_argument(
        "--docling-json",
        type=Path,
        default=None,
        help="Optional path to pre-exported Docling JSON (skips Docling parsing step).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_pdf = args.input_pdf.expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    if args.output_pdf is None:
        output_pdf = (
            Path(__file__).resolve().parent
            / DEFAULT_OUTPUT_DIR
            / f"{input_pdf.stem}.annotated.pdf"
        )
    else:
        output_pdf = args.output_pdf.expanduser().resolve()

    total, drawn = annotate_pdf(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        stroke_width=args.stroke_width,
        docling_json=args.docling_json.expanduser().resolve() if args.docling_json else None,
    )
    print(f"Input: {input_pdf}")
    print(f"Output: {output_pdf}")
    print(f"Elements found: {total}")
    print(f"Boxes drawn: {drawn}")


if __name__ == "__main__":
    main()
