"""
PDF Cleaner — Pre-processing step for the LlamaParse benchmark.

Opens each PDF in data/document_diversity/, detects repeating header/footer
text blocks via coordinate analysis, crops all pages to exclude those
zones, and writes cleaned PDFs to data/document_diversity_clean/.

Usage:
    python pdf_cleaner.py
"""

import re
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

from text_cleaning import _normalize

# =========================
# CONFIGURATION
# =========================
INPUT_DIR = Path("data/document_diversity")
OUTPUT_DIR = Path("data/document_diversity_clean")

# How many pages to sample when detecting repeating header/footer blocks
SAMPLE_PAGES = 8

# A text block must repeat on at least this fraction of sampled pages
# to be considered a header/footer  (e.g. 0.5 = appears on >= 50 % of pages)
MIN_REPEAT_FRACTION = 0.5

# Extra margin (in points) added above/below the detected noise zone
# to make sure we fully exclude the header/footer area
MARGIN_BUFFER_PT = 4


# =========================
# DETECTION HELPERS
# =========================

def _extract_block_text(blk: dict) -> str:
    """Concatenate all span text in a block dict."""
    raw = ""
    for line in blk.get("lines", []):
        for span in line.get("spans", []):
            raw += span.get("text", "")
        raw += " "
    return raw.strip()


def detect_header_footer_zones(doc: fitz.Document) -> tuple[float | None, float | None]:
    """
    Analyse the first SAMPLE_PAGES pages of *doc* and return
    (header_bottom_y, footer_top_y) — the y-coordinates that delimit
    the zones to crop.  Returns None for a zone if nothing was detected.

    Strategy:
      1. For each page, extract text blocks with bounding boxes.
      2. Normalise the text content (digits → #) and record positions.
      3. Blocks whose normalised content repeats on >= MIN_REPEAT_FRACTION
         of pages AND that sit in the top 15 % or bottom 15 % of the page
         height are flagged as header/footer candidates.
      4. Blocks that span > 40 % of the page height are treated as
         watermarks and skipped (they overlap body content and cannot
         be removed by cropping — handled by post-processing instead).
      5. The crop boundaries are the max(bottom of header blocks) and
         min(top of footer blocks) across pages.
    """
    num_pages = min(len(doc), SAMPLE_PAGES)
    if num_pages < 2:
        return None, None

    page_height = doc[0].rect.height
    top_zone = page_height * 0.15      # top 15 %
    bottom_zone = page_height * 0.85   # bottom 15 %
    watermark_threshold = page_height * 0.40  # skip blocks taller than this

    # Collect (normalised text → list of (page_idx, y0, y1))
    block_locations: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    for page_idx in range(num_pages):
        page = doc[page_idx]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for blk in blocks:
            if blk["type"] != 0:  # skip image blocks
                continue
            raw = _extract_block_text(blk)
            norm = _normalize(raw)
            if not norm or len(norm) < 3:
                continue
            y0, y1 = blk["bbox"][1], blk["bbox"][3]
            block_locations[norm].append((page_idx, y0, y1))

    min_repeats = max(2, int(num_pages * MIN_REPEAT_FRACTION))

    header_bottom_y: float | None = None
    footer_top_y: float | None = None

    for norm_text, locs in block_locations.items():
        # Count distinct pages this block appears on
        pages_seen = len({pg for pg, _, _ in locs})
        if pages_seen < min_repeats:
            continue

        for _, y0, y1 in locs:
            block_height = y1 - y0
            # Skip watermark-style blocks that span most of the page
            if block_height > watermark_threshold:
                continue
            # Header candidate: sits in top zone
            if y0 < top_zone:
                if header_bottom_y is None or y1 > header_bottom_y:
                    header_bottom_y = y1
            # Footer candidate: sits in bottom zone
            if y0 > bottom_zone:
                if footer_top_y is None or y0 < footer_top_y:
                    footer_top_y = y0

    return header_bottom_y, footer_top_y


# =========================
# FIGURE / IMAGE REDACTION
# =========================

# Minimum image area (in pt^2) to consider for redaction.
# Smaller images (icons, logos, bullets) are left alone.
MIN_IMAGE_AREA_PT2 = 8_000  # roughly 90x90 pt

# Minimum number of drawing paths in a region to consider it a vector figure
MIN_DRAWING_PATHS_FOR_FIGURE = 8

# Minimum area of a drawing cluster to be considered a figure
MIN_DRAWING_AREA_PT2 = 12_000  # roughly 110x110 pt


def _get_text_blocks_on_page(page: fitz.Page) -> list[fitz.Rect]:
    """Return bounding rects of all text blocks on a page."""
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    rects = []
    for blk in blocks:
        if blk["type"] == 0:  # text block
            rects.append(fitz.Rect(blk["bbox"]))
    return rects


def _cluster_drawings(paths: list[dict], gap: float = 15.0) -> list[fitz.Rect]:
    """
    Cluster drawing paths into contiguous figure regions.

    Merges overlapping or nearby (within *gap* pt) drawing bounding boxes
    into clusters. Returns a list of cluster bounding rects.
    """
    if not paths:
        return []

    # Start with individual drawing rects
    rects = [fitz.Rect(p["rect"]) for p in paths]
    # Filter out tiny paths (lines, dots)
    rects = [r for r in rects if r.width > 3 and r.height > 3]
    if not rects:
        return []

    # Greedy merge: keep merging overlapping/nearby rects until stable
    changed = True
    while changed:
        changed = False
        merged = []
        used = [False] * len(rects)
        for i in range(len(rects)):
            if used[i]:
                continue
            current = fitz.Rect(rects[i])
            for j in range(i + 1, len(rects)):
                if used[j]:
                    continue
                expanded = fitz.Rect(
                    current.x0 - gap, current.y0 - gap,
                    current.x1 + gap, current.y1 + gap,
                )
                if expanded.intersects(rects[j]):
                    current |= rects[j]  # union
                    used[j] = True
                    changed = True
            merged.append(current)
        rects = merged

    return rects


def detect_figures(page: fitz.Page) -> list[fitz.Rect]:
    """
    Detect figure regions on a page using two strategies:

    1. **Raster images**: any embedded image larger than MIN_IMAGE_AREA_PT2.
    2. **Vector figures**: clusters of drawing paths that cover a large area
       and contain little or no text (i.e., the region is mostly graphical).

    Returns a list of fitz.Rect bounding boxes for detected figures.
    """
    figure_rects: list[fitz.Rect] = []
    page_rect = page.rect

    # --- Strategy 1: Raster images ---
    images = page.get_images(full=True)
    for img in images:
        xref = img[0]
        try:
            img_rects = page.get_image_rects(xref)
        except Exception:
            continue
        for r in img_rects:
            if r.is_empty or r.is_infinite:
                continue
            if r.width * r.height >= MIN_IMAGE_AREA_PT2:
                figure_rects.append(r)

    # --- Strategy 2: Vector drawing clusters ---
    paths = page.get_drawings()
    if len(paths) >= MIN_DRAWING_PATHS_FOR_FIGURE:
        clusters = _cluster_drawings(paths)
        text_blocks = _get_text_blocks_on_page(page)

        for cluster_rect in clusters:
            area = cluster_rect.width * cluster_rect.height
            if area < MIN_DRAWING_AREA_PT2:
                continue

            # Skip if cluster spans most of the page width AND height
            # (likely decorative borders, column rules, or background)
            if (cluster_rect.width > page_rect.width * 0.9 and
                    cluster_rect.height > page_rect.height * 0.7):
                continue

            # Check how much text overlaps with this cluster
            text_overlap_area = 0.0
            for tb in text_blocks:
                intersection = cluster_rect & tb  # rect intersection
                if not intersection.is_empty:
                    text_overlap_area += intersection.width * intersection.height

            text_fraction = text_overlap_area / max(1, area)

            # If less than 20% of the cluster area is text, it's likely a figure
            if text_fraction < 0.20:
                figure_rects.append(cluster_rect)

    return figure_rects


def redact_figures(doc: fitz.Document) -> int:
    """
    Detect and redact (white-out) figure regions on all pages.

    Returns the total number of figures redacted.
    """
    total_redacted = 0

    for page in doc:
        figures = detect_figures(page)
        for fig_rect in figures:
            # Add a small margin around the figure
            expanded = fitz.Rect(
                fig_rect.x0 - 2, fig_rect.y0 - 2,
                fig_rect.x1 + 2, fig_rect.y1 + 2,
            )
            # Clip to page bounds
            expanded &= page.rect
            if expanded.is_empty:
                continue
            page.add_redact_annot(expanded, fill=(1, 1, 1))  # white fill
            total_redacted += 1

        if figures:
            page.apply_redactions()

    return total_redacted


# =========================
# COLUMN LINEARIZATION
# =========================

# Minimum number of text blocks in each column to consider a page two-column
MIN_COLUMN_BLOCKS = 2

# A block wider than this fraction of the page width is considered "full-width"
FULL_WIDTH_FRACTION = 0.60

# Minimum gap (pt) between columns to confirm a gutter exists
MIN_GUTTER_GAP_PT = 8


def detect_page_columns(
    page: fitz.Page,
) -> tuple[float, list[fitz.Rect], list[fitz.Rect], list[fitz.Rect]] | None:
    """
    Detect whether *page* has a two-column text layout.

    Returns ``None`` if the page is single-column, or a tuple of:
      (gutter_x, left_block_rects, right_block_rects, full_width_rects)
    """
    pw = page.rect.width
    page_mid = pw / 2

    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    text_blocks = [b for b in blocks if b["type"] == 0]

    if len(text_blocks) < 3:
        return None

    left_rects: list[fitz.Rect] = []
    right_rects: list[fitz.Rect] = []
    full_rects: list[fitz.Rect] = []

    for b in text_blocks:
        rect = fitz.Rect(b["bbox"])
        width = rect.width

        # Skip tiny fragments (page numbers, single characters)
        if width < 30:
            continue

        center_x = (rect.x0 + rect.x1) / 2

        if width > pw * FULL_WIDTH_FRACTION:
            full_rects.append(rect)
        elif center_x < page_mid:
            left_rects.append(rect)
        else:
            right_rects.append(rect)

    # Need enough blocks in both columns
    if len(left_rects) < MIN_COLUMN_BLOCKS or len(right_rects) < MIN_COLUMN_BLOCKS:
        return None

    # Verify a clear gutter exists (left blocks don't overlap right blocks)
    max_left_x1 = max(r.x1 for r in left_rects)
    min_right_x0 = min(r.x0 for r in right_rects)

    if (min_right_x0 - max_left_x1) < MIN_GUTTER_GAP_PT:
        return None  # columns overlap — not a clean two-column layout

    gutter_x = (max_left_x1 + min_right_x0) / 2
    return gutter_x, left_rects, right_rects, full_rects


def linearize_columns(doc: fitz.Document) -> int:
    """
    Split two-column pages into two single-column pages so that
    downstream parsers read content in the correct order:
      full-width blocks + left column  →  right column.

    For each detected two-column page the function:
      1. Duplicates the page.
      2. On the original page, redacts (white-out) the right-column blocks.
      3. On the copy (inserted after), redacts full-width + left-column blocks.

    Pages are processed in reverse order so that index shifts from insertions
    don't affect earlier pages.

    Returns the number of pages that were split.
    """
    # Phase 1: detect which pages need splitting
    split_plan: list[
        tuple[int, float, list[fitz.Rect], list[fitz.Rect], list[fitz.Rect]]
    ] = []

    for pg_idx in range(len(doc)):
        result = detect_page_columns(doc[pg_idx])
        if result is not None:
            gutter_x, left_rects, right_rects, full_rects = result
            split_plan.append((pg_idx, gutter_x, left_rects, right_rects, full_rects))

    if not split_plan:
        return 0

    # Phase 2: split pages (reverse order keeps earlier indices stable)
    for pg_idx, gutter_x, left_rects, right_rects, full_rects in reversed(split_plan):
        # Deep-copy the page via a temporary document so that the copy
        # has an independent content stream (copy_page shares streams,
        # meaning redactions on one would erase text on the other).
        temp_doc = fitz.open()
        temp_doc.insert_pdf(doc, from_page=pg_idx, to_page=pg_idx)
        doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=pg_idx + 1)
        temp_doc.close()

        # --- Original page (pg_idx): hide RIGHT column ---
        orig_page = doc[pg_idx]
        for rect in right_rects:
            expanded = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
            expanded &= orig_page.rect
            if not expanded.is_empty:
                orig_page.add_redact_annot(expanded, fill=(1, 1, 1))
        if right_rects:
            orig_page.apply_redactions()

        # --- Copy page (pg_idx + 1): hide FULL-WIDTH + LEFT column ---
        copy_page = doc[pg_idx + 1]
        for rect in full_rects + left_rects:
            expanded = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
            expanded &= copy_page.rect
            if not expanded.is_empty:
                copy_page.add_redact_annot(expanded, fill=(1, 1, 1))
        if full_rects or left_rects:
            copy_page.apply_redactions()

    return len(split_plan)


# =========================
# CROP AND SAVE
# =========================

def crop_pdf(
    input_path: Path,
    output_path: Path,
    remove_figures: bool = True,
    do_linearize_columns: bool = False,
) -> dict:
    """
    Open *input_path*, detect header/footer zones, crop every page,
    optionally redact figures and linearize two-column layouts,
    and save the result to *output_path*.

    Returns a summary dict with detection details.
    """
    doc = fitz.open(str(input_path))
    header_bottom, footer_top = detect_header_footer_zones(doc)

    summary = {
        "filename": input_path.name,
        "pages": len(doc),
        "header_bottom_y": round(header_bottom, 1) if header_bottom else None,
        "footer_top_y": round(footer_top, 1) if footer_top else None,
        "cropped": False,
        "figures_redacted": 0,
        "columns_split": 0,
    }

    # --- Step 1: Redact figures (before cropping, so coordinates are original) ---
    if remove_figures:
        summary["figures_redacted"] = redact_figures(doc)

    # --- Step 2: Crop headers/footers ---
    if header_bottom is not None or footer_top is not None:
        summary["cropped"] = True

        for page in doc:
            rect = page.rect
            new_y0 = (header_bottom + MARGIN_BUFFER_PT) if header_bottom else rect.y0
            new_y1 = (footer_top - MARGIN_BUFFER_PT) if footer_top else rect.y1

            # Safety: don't let the crop leave less than 50 % of the page
            if (new_y1 - new_y0) < rect.height * 0.5:
                print(f"  [WARN] {input_path.name} p{page.number}: crop too aggressive, skipping")
                continue

            page.set_cropbox(fitz.Rect(rect.x0, new_y0, rect.x1, new_y1))

    # --- Step 3: Linearize columns (after crop so header/footer blocks are gone) ---
    if do_linearize_columns:
        summary["columns_split"] = linearize_columns(doc)

    num_pages = len(doc)
    doc.save(str(output_path))
    doc.close()

    # --- Report ---
    parts = []
    if summary["cropped"]:
        h_info = f"header→{summary['header_bottom_y']}pt" if header_bottom else "no header"
        f_info = f"footer→{summary['footer_top_y']}pt" if footer_top else "no footer"
        parts.append(f"{h_info}, {f_info}")
    if summary["figures_redacted"] > 0:
        parts.append(f"{summary['figures_redacted']} figures redacted")
    if summary["columns_split"] > 0:
        parts.append(f"{summary['columns_split']} pages column-split")

    if parts:
        print(f"  [CLEAN] {input_path.name} ({num_pages} pages): {', '.join(parts)}")
    else:
        print(f"  [SKIP] {input_path.name} — no header/footer, figures, or columns detected")

    return summary


# =========================
# MAIN
# =========================

OUTPUT_DIR_COLUMN = Path("data/document_diversity_column")


def main():
    """Run the full cleaning pipeline: clean + column-linearized variants."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR_COLUMN.mkdir(exist_ok=True)

    pdf_files = sorted(f for f in INPUT_DIR.iterdir() if f.suffix.lower() == ".pdf")
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}/")
        return

    # ---- Pass 1: clean PDFs (header/footer crop + figure redaction) ----
    print(f"PDF Cleaner: processing {len(pdf_files)} files from {INPUT_DIR}/\n")
    print(f"--- Pass 1: Clean (crop + figure redaction) → {OUTPUT_DIR}/ ---")

    summaries_clean = []
    for pdf_path in pdf_files:
        output_path = OUTPUT_DIR / pdf_path.name
        summary = crop_pdf(pdf_path, output_path, remove_figures=True, do_linearize_columns=False)
        summaries_clean.append(summary)

    cropped_count = sum(1 for s in summaries_clean if s["cropped"])
    fig_count = sum(s["figures_redacted"] for s in summaries_clean)
    print(f"\n  → {cropped_count}/{len(summaries_clean)} PDFs cropped, {fig_count} figures redacted.")

    # ---- Pass 2: column-linearized PDFs (clean + column splitting) ----
    print(f"\n--- Pass 2: Column-linearized (clean + column split) → {OUTPUT_DIR_COLUMN}/ ---")

    summaries_column = []
    for pdf_path in pdf_files:
        output_path = OUTPUT_DIR_COLUMN / pdf_path.name
        summary = crop_pdf(pdf_path, output_path, remove_figures=True, do_linearize_columns=True)
        summaries_column.append(summary)

    col_count = sum(1 for s in summaries_column if s["columns_split"] > 0)
    total_split = sum(s["columns_split"] for s in summaries_column)
    print(f"\n  → {col_count}/{len(summaries_column)} PDFs had columns linearized ({total_split} pages split).")
    print(f"\nDone. Output in {OUTPUT_DIR}/ and {OUTPUT_DIR_COLUMN}/")


if __name__ == "__main__":
    main()
