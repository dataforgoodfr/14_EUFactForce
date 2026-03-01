import os
import re
import sys
import time
import csv
import argparse
import json
from pathlib import Path

import fitz  # PyMuPDF
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.llama_parse import LlamaParse
from docling.document_converter import DocumentConverter
from hierarchical.postprocessor import ResultPostprocessor
from text_cleaning import postprocess_text

load_dotenv()

# =========================
# CONFIGURATION
# =========================
INPUT_FOLDER_RAW = "data/document_diversity"
INPUT_FOLDER_PREPROCESSED = "data/document_diversity_clean"
INPUT_FOLDER_COLUMN = "data/document_diversity_column"
OUTPUT_CSV = "output/benchmark_results_extended.csv"
EXTRACTED_TEXT_DIR = "output/extracted_texts"
LLAMAPARSE_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
GROUND_TRUTH_FILE = Path("ground_truth/ground_truth.json")

# Heuristic thresholds for metadata detection
MIN_TITLE_LENGTH = 10
MAX_TITLE_LENGTH = 300
TITLE_SCAN_LINES = 10
AUTHOR_CHUNK_CHARS = 2000
FIRST_CHUNK_CHARS = 5000
ERROR_MSG_MAX_CHARS = 200
DOCLING_PYMUPDF_MIN_TOKEN_OVERLAP_RATIO = 0.2
DOCLING_PYMUPDF_MIN_SHARED_TOKENS = 1
DOCLING_PICTURE_OVERLAP_DROP_RATIO = 0.6
DOCLING_PICTURE_OVERLAP_BLOCK_RATIO = 0.5
DOCLING_GLOBAL_SNIPPET_REMOVE_MIN_CHARS = 20
DOCLING_SMALL_BOX_MAX_AREA_RATIO = 0.0015
DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS = 2

# Parser configurations to benchmark
CONFIGS = {
    "llamaparse_text": {"type": "llamaparse", "result_type": "text"},
    "llamaparse_markdown": {"type": "llamaparse", "result_type": "markdown"},
    "pymupdf": {"type": "pymupdf"},
    "docling_text": {"type": "docling", "result_type": "text", "postprocess": True},
    "docling_markdown": {"type": "docling", "result_type": "markdown", "postprocess": True},
    "docling_markdown_indexing": {
        "type": "docling",
        "result_type": "markdown",
        "postprocess": True,
        "indexing_cleanup": True,
    },
}

# Benchmark config profiles (used via --profile).
CONFIG_PROFILES: dict[str, list[str]] = {
    "full": list(CONFIGS.keys()),
    # Faster profile keeping one markdown-first representative per parser family.
    "fast": [
        "pymupdf",
        "docling_markdown",
        "llamaparse_markdown",
    ],
    # Useful for Docling-only tuning loops.
    "docling_only": [
        "docling_text",
        "docling_markdown",
        "docling_markdown_indexing",
    ],
}

# Front-matter labels that hierarchical postprocessing can demote to plain text.
_DEMOTED_HEADER_LABELS = {
    "review",
    "abstract",
    "addresses",
    "keywords",
}

# =========================
# METADATA DETECTION
# =========================

def detect_doi(text: str) -> str:
    """Search for a DOI pattern (e.g. 10.1234/...) anywhere in extracted text."""
    return "found" if re.search(r"10\.\d{4,}/\S+", text) else "not_found"


def detect_abstract(text: str) -> str:
    """Check whether the word 'Abstract' appears as a section heading."""
    return "found" if re.search(r"\babstract\b", text, re.IGNORECASE) else "not_found"


def detect_references(text: str) -> str:
    """Check whether a 'References' section exists (typically at the end)."""
    return "found" if re.search(r"\breferences\b", text, re.IGNORECASE) else "not_found"


def detect_title(first_chunk: str) -> str:
    """Heuristic: a title-like line should appear in the first few lines."""
    for line in first_chunk.strip().splitlines()[:TITLE_SCAN_LINES]:
        stripped = line.strip()
        if MIN_TITLE_LENGTH < len(stripped) < MAX_TITLE_LENGTH:
            return "found"
    return "not_found"


def detect_authors(first_chunk: str) -> str:
    """Heuristic: look for name-like patterns or 'Author(s):' in the first N chars."""
    snippet = first_chunk[:AUTHOR_CHUNK_CHARS]
    patterns = [
        r"[A-Z][a-z]+\s+[A-Z][a-z]+",         # Firstname Lastname
        r"(?:authors?|by)\s*:",                  # Explicit label for authors
        r"[A-Z]\.\s*[A-Z][a-z]+",               # J. Smith
    ]
    for pat in patterns:
        if re.search(pat, snippet):
            return "found"
    return "not_found"


def compute_metadata_score(record: dict) -> int:
    """Count how many of the 5 metadata fields were detected."""
    fields = ["has_doi", "has_abstract", "has_references", "has_title", "has_authors"]
    return sum(1 for f in fields if record.get(f) == "found")


# =========================
# PARSING HELPERS
# =========================

def parse_llamaparse(file_path: Path, result_type: str):
    """Parse a PDF with LlamaParse and return (full_text, first_chunk, pages, num_docs)."""
    parser = LlamaParse(api_key=LLAMAPARSE_API_KEY, result_type=result_type)
    reader = SimpleDirectoryReader(
        input_files=[str(file_path)],
        file_extractor={".pdf": parser},
    )
    documents = reader.load_data()

    full_text = "\n".join(d.text for d in documents)
    first_chunk = documents[0].text if documents else ""

    if documents and "page_label" in documents[0].metadata:
        pages = len({d.metadata.get("page_label") for d in documents})
    else:
        pages = len(documents)

    return full_text, first_chunk, pages, len(documents)


def parse_pymupdf(file_path: Path):
    """Parse a PDF with PyMuPDF and return (full_text, first_chunk, pages, num_docs)."""
    doc = fitz.open(str(file_path))
    page_texts = [doc[i].get_text() for i in range(len(doc))]
    pages = len(doc)
    doc.close()

    full_text = "\n".join(page_texts)
    first_chunk = page_texts[0] if page_texts else ""
    return full_text, first_chunk, pages, pages  # one "document" per page


def parse_docling(
    file_path: Path,
    result_type: str,
    postprocess: bool,
    validate_text_bboxes: bool = False,
):
    """Parse a PDF with Docling and return (full_text, first_page text, pages, num_docs)."""
    parser = DocumentConverter()
    result = parser.convert(file_path)
    if postprocess is True:
        ResultPostprocessor(result).process()
    doc_dict = result.document.export_to_dict()

    if validate_text_bboxes:
        dropped_blocks, first_page_text, stats = _collect_docling_ghost_text_blocks(
            file_path=file_path,
            result=result,
            doc_dict=doc_dict,
        )
        if result_type == 'text':
            full_text = result.document.export_to_text()
        elif result_type == 'markdown':
            full_text = result.document.export_to_markdown()
            full_text = _normalize_markdown_headers_for_gt(full_text)
        else:
            raise NotImplementedError(f"Unknown result_type: {result_type}")

        full_text = _remove_dropped_docling_snippets(full_text, dropped_blocks)
        full_text = _relocate_docling_labeled_footnotes(full_text, doc_dict, result_type)
        print(
            "[docling-bbox-filter] "
            f"{file_path.name}: dropped {stats['dropped_text_blocks']}/"
            f"{stats['considered_text_blocks']} text blocks without real PDF words"
        )
    else:
        if result_type == 'text':
            full_text = result.document.export_to_text()
        elif result_type == 'markdown':
            full_text = result.document.export_to_markdown()
            full_text = _normalize_markdown_headers_for_gt(full_text)
        else:
            raise NotImplementedError(f"Unknown result_type: {result_type}")
        full_text = _relocate_docling_labeled_footnotes(full_text, doc_dict, result_type)
        
        first_page_text = "\n".join(
            [x['text'] for x in doc_dict['texts'] if x['prov'][0]['page_no'] == 1]
        )

    return full_text, first_page_text, len(result.pages), 1 # One PDF document per call


def _docling_bbox_to_rect(bbox: dict, page_height: float) -> fitz.Rect:
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

    return fitz.Rect(min(left, right), y_top, max(left, right), y_bottom)


def _rect_overlap_ratio(inner: fitz.Rect, outer: fitz.Rect) -> float:
    """Return intersection area over inner rect area."""
    if inner.is_empty or outer.is_empty or inner.width <= 0 or inner.height <= 0:
        return 0.0
    inter = inner & outer
    if inter.is_empty:
        return 0.0
    return max(0.0, (inter.width * inter.height) / (inner.width * inner.height))


def _rect_area_ratio(rect: fitz.Rect, page_rect: fitz.Rect) -> float:
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


def _build_docling_picture_regions_by_page(doc_dict: dict, pdf: fitz.Document) -> dict[int, list[fitz.Rect]]:
    """
    Build picture regions by page from Docling dict.

    We treat text blocks mostly inside these regions as image OCR noise.
    """
    regions: dict[int, list[fitz.Rect]] = {}
    for item in doc_dict.get("pictures", []):
        for prov in item.get("prov", []):
            bbox = prov.get("bbox")
            if not bbox:
                continue
            page_no = int(prov.get("page_no", 1))
            page_idx = page_no - 1
            if page_idx < 0 or page_idx >= len(pdf):
                continue
            rect = _docling_bbox_to_rect(bbox, pdf[page_idx].rect.height)
            regions.setdefault(page_no, []).append(rect)
    return regions


def _rect_has_pdf_words(page: fitz.Page, rect: fitz.Rect, min_tokens: int = 1) -> bool:
    """Check whether a PDF rect contains real extractable word tokens."""
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        return False

    words = page.get_text("words", clip=rect)
    if not words:
        return False

    token_count = 0
    for word in words:
        token = str(word[4]).strip()
        # Require at least one alphanumeric to avoid punctuation-only artifacts.
        if token and re.search(r"[A-Za-z0-9]", token):
            token_count += 1
            if token_count >= min_tokens:
                return True
    return False


def _tokenize_for_overlap(text: str) -> set[str]:
    """Tokenize text for lightweight agreement checks."""
    return {
        tok
        for tok in re.findall(r"[A-Za-z0-9]{2,}", text.lower())
        if len(tok) >= 2
    }


def _bbox_word_tokens(page: fitz.Page, rect: fitz.Rect) -> set[str]:
    """Extract normalized word tokens from a PDF rectangle."""
    words = page.get_text("words", clip=rect)
    if not words:
        return set()
    raw = " ".join(str(w[4]) for w in words if str(w[4]).strip())
    return _tokenize_for_overlap(raw)


def _docling_text_agrees_with_pdf_words(
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

    docling_tokens = _tokenize_for_overlap(docling_text)
    if not docling_tokens:
        return False

    shared = docling_tokens.intersection(pdf_tokens)
    if len(shared) < min_shared_tokens:
        return False

    overlap_ratio = len(shared) / max(1, len(docling_tokens))
    return overlap_ratio >= min_overlap_ratio


def _collect_docling_ghost_text_blocks(
    file_path: Path,
    result,
    doc_dict: dict,
) -> tuple[list[dict[str, object]], str, dict[str, int]]:
    """
    Identify Docling text blocks whose bboxes map to no real PDF words.

    This mitigates ghost Docling text regions in highly stylized PDFs.
    """
    text_items = doc_dict.get("texts", [])

    pdf = fitz.open(str(file_path))
    picture_regions = _build_docling_picture_regions_by_page(doc_dict, pdf)
    kept_blocks: list[tuple[int, str]] = []
    dropped_blocks: list[dict[str, object]] = []
    dropped = 0
    considered = 0

    for item in text_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        provs = item.get("prov", [])
        label = str(item.get("label", "text")).strip().lower()
        considered += 1

        # Keep blocks without provenance to avoid accidental data loss.
        if not provs:
            kept_blocks.append((1, text))
            continue

        keep = False
        page_no_for_order = 1
        prov_count = 0
        prov_inside_picture_count = 0
        max_bbox_area_ratio = 0.0
        for prov in provs:
            bbox = prov.get("bbox")
            page_no = int(prov.get("page_no", 1))
            page_no_for_order = page_no
            if not bbox:
                continue
            prov_count += 1
            page_idx = page_no - 1
            if page_idx < 0 or page_idx >= len(pdf):
                continue
            rect = _docling_bbox_to_rect(bbox, pdf[page_idx].rect.height)
            max_bbox_area_ratio = max(
                max_bbox_area_ratio,
                _rect_area_ratio(rect, pdf[page_idx].rect),
            )

            # Track how often this text block falls inside picture regions.
            if label != "caption":
                pic_rects = picture_regions.get(page_no, [])
                inside_picture = any(
                    _rect_overlap_ratio(rect, pic_rect) >= DOCLING_PICTURE_OVERLAP_DROP_RATIO
                    for pic_rect in pic_rects
                )
                if inside_picture:
                    prov_inside_picture_count += 1
                    continue

            if not _rect_has_pdf_words(pdf[page_idx], rect):
                continue

            pdf_tokens = _bbox_word_tokens(pdf[page_idx], rect)
            if _docling_text_agrees_with_pdf_words(text, pdf_tokens):
                keep = True
                break

        # Generic Docling-geometry rule: if most provenance boxes of a text block
        # are inside picture regions, treat it as OCR from image content.
        if label != "caption" and prov_count > 0:
            picture_ratio = prov_inside_picture_count / prov_count
            if picture_ratio >= DOCLING_PICTURE_OVERLAP_BLOCK_RATIO:
                keep = False

        if keep:
            kept_blocks.append((page_no_for_order, text))
        else:
            dropped_blocks.append(
                {
                    "text": text,
                    "is_small_box": max_bbox_area_ratio <= DOCLING_SMALL_BOX_MAX_AREA_RATIO,
                }
            )
            dropped += 1

    pdf.close()

    first_page_parts: list[str] = []
    for page_no, text in kept_blocks:
        if page_no == 1:
            first_page_parts.append(text)

    first_page_text = "\n".join(first_page_parts)
    stats = {
        "considered_text_blocks": considered,
        "dropped_text_blocks": dropped,
    }
    return dropped_blocks, first_page_text, stats


def _remove_dropped_docling_snippets(
    rendered_text: str,
    dropped_blocks: list[dict[str, object]],
) -> str:
    """
    Remove dropped ghost snippets from Docling-rendered output while keeping
    Docling's original markdown formatting for surviving content.
    """
    cleaned = rendered_text
    global_snippets: set[str] = set()
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

        if len(snippet) >= DOCLING_GLOBAL_SNIPPET_REMOVE_MIN_CHARS:
            global_snippets.add(snippet)
        elif len(snippet) >= DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS:
            # For non-small dropped snippets that are too short for safe global
            # replacement, fall back to exact-line removal.
            non_small_line_snippets.add(snippet)

    # Non-small dropped boxes use global replacement (longest first).
    for snippet in sorted(global_snippets, key=len, reverse=True):
        cleaned = cleaned.replace(snippet, "")

    # Remove short dropped snippets only when they appear as exact line text.
    line_snippets = small_box_line_snippets.union(non_small_line_snippets)
    if line_snippets:
        kept_lines: list[str] = []
        for line in cleaned.splitlines():
            if line.strip() in line_snippets:
                continue
            kept_lines.append(line)
        cleaned = "\n".join(kept_lines)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _docling_snippet_variants(snippet: str) -> list[str]:
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


def _relocate_docling_labeled_footnotes(
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
        for candidate in _docling_snippet_variants(snippet):
            if candidate in cleaned:
                cleaned = cleaned.replace(candidate, "")
                removed = True
        if removed:
            kept_footnotes.append(snippet)

    if not kept_footnotes:
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if result_type == "markdown":
        section_title = "# Footnotes"
    else:
        section_title = "Footnotes"
    return f"{cleaned}\n\n{section_title}\n\n" + "\n\n".join(kept_footnotes)


def _normalize_markdown_headers_for_gt(markdown_text: str) -> str:
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

        # Downgrade any markdown heading depth to level-1.
        m = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if m:
            normalized.append(f"# {m.group(1).strip()}")
            continue

        # Promote known demoted header labels to level-1 headings.
        if stripped.lower() in _DEMOTED_HEADER_LABELS:
            normalized.append(f"# {stripped}")
            continue

        normalized.append(line)

    return "\n".join(normalized)

# =========================
# BENCHMARK FUNCTION
# =========================

def run_benchmark(
    input_folder: str,
    config_suffix: str = "",
    skip_existing: bool = False,
    selected_configs: list[str] | None = None,
    allowed_filenames: set[str] | None = None,
    docling_validate_bboxes: bool = False,
) -> list[dict]:
    """
    Run all parser configurations on PDFs in *input_folder*.

    If *config_suffix* is provided (e.g. '_preprocessed'), it is appended to each
    parser_config name in the output records and extracted text filenames.

    If *skip_existing* is True, skip any (file, config) combination whose
    extracted-text file already exists, and reconstruct the record from it.

    Returns a list of result records.
    """
    input_path = Path(input_folder)
    if not input_path.exists():
        print(f"[WARN] Input folder {input_folder} not found — skipping.")
        return []

    files = sorted(f for f in input_path.iterdir() if f.suffix.lower() == ".pdf")
    if allowed_filenames is not None:
        files = [f for f in files if f.name in allowed_filenames]
    if not files:
        print(f"[WARN] No PDF files in {input_folder} — skipping.")
        return []

    Path(EXTRACTED_TEXT_DIR).mkdir(exist_ok=True)
    results = []

    label = f" ({config_suffix.strip('_')})" if config_suffix else ""
    print(f"\n{'='*60}")
    print(f"Benchmarking {len(files)} PDFs from {input_folder}/{label}")
    print(f"{'='*60}\n")

    active_config_names = selected_configs if selected_configs is not None else list(CONFIGS.keys())
    doc_type_map = _load_doc_type_map()
    for file_path in files:
        file_doc_type = doc_type_map.get(file_path.name)
        for config_name in active_config_names:
            config = CONFIGS[config_name]
            output_config_name = f"{config_name}{config_suffix}"
            out_file = Path(EXTRACTED_TEXT_DIR) / f"{file_path.stem}__{output_config_name}.txt"

            # ---- Cache: reuse existing extracted text ----
            if skip_existing and out_file.exists():
                full_text = out_file.read_text(encoding="utf-8")
                first_chunk = full_text[:FIRST_CHUNK_CHARS]
                # Estimate pages from PDF
                try:
                    doc = fitz.open(str(file_path))
                    pages = len(doc)
                    doc.close()
                except Exception:
                    pages = 1

                word_count = len(full_text.split())
                char_count = len(full_text)

                record = {
                    "filename": file_path.name,
                    "parser_config": output_config_name,
                    "pages": pages,
                    "parse_time_s": None,
                    "time_per_page": None,
                    "word_count": word_count,
                    "char_count": char_count,
                    "num_documents": None,
                    "has_doi": detect_doi(full_text),
                    "has_abstract": detect_abstract(full_text),
                    "has_references": detect_references(full_text),
                    "has_title": detect_title(first_chunk),
                    "has_authors": detect_authors(first_chunk),
                    "metadata_score": 0,
                    "status": "success (cached)",
                }
                record["metadata_score"] = compute_metadata_score(record)
                results.append(record)
                print(f"[{output_config_name}] {file_path.name} — cached ✓")
                continue

            print(f"[{output_config_name}] Processing {file_path.name} ...")

            record = {
                "filename": file_path.name,
                "parser_config": output_config_name,
                "pages": None,
                "parse_time_s": None,
                "time_per_page": None,
                "word_count": None,
                "char_count": None,
                "num_documents": None,
                "has_doi": "not_found",
                "has_abstract": "not_found",
                "has_references": "not_found",
                "has_title": "not_found",
                "has_authors": "not_found",
                "metadata_score": 0,
                "status": "error",
            }

            try:
                start = time.perf_counter()

                if config["type"] == "llamaparse":
                    full_text, first_chunk, pages, num_docs = parse_llamaparse(
                        file_path, config["result_type"]
                    )
                elif config["type"] == "docling":
                    full_text, first_chunk, pages, num_docs = parse_docling(
                        file_path,
                        config["result_type"],
                        config["postprocess"],
                        validate_text_bboxes=docling_validate_bboxes,
                    )
                else:  # pymupdf
                    full_text, first_chunk, pages, num_docs = parse_pymupdf(file_path)

                parse_time = time.perf_counter() - start

                # ---- Volume metrics ----
                word_count = len(full_text.split())
                char_count = len(full_text)
                time_per_page = round(parse_time / pages, 3) if pages else None

                # ---- Metadata detection ----
                record["has_doi"] = detect_doi(full_text)
                record["has_abstract"] = detect_abstract(full_text)
                record["has_references"] = detect_references(full_text)
                record["has_title"] = detect_title(first_chunk)
                record["has_authors"] = detect_authors(first_chunk)
                record["metadata_score"] = compute_metadata_score(record)

                # ---- Post-process: fix encoding artifacts, rejoin hyphens ----
                full_text = postprocess_text(
                    full_text,
                    doc_type=file_doc_type,
                    indexing_cleanup=bool(config.get("indexing_cleanup", False)),
                )
                first_chunk = full_text[:FIRST_CHUNK_CHARS]

                # ---- Save extracted text for later quality review ----
                out_file.write_text(full_text, encoding="utf-8")

                record.update(
                    {
                        "pages": pages,
                        "parse_time_s": round(parse_time, 2),
                        "time_per_page": time_per_page,
                        "word_count": word_count,
                        "char_count": char_count,
                        "num_documents": num_docs,
                        "status": "success",
                    }
                )

            except Exception as e:
                record["status"] = f"error: {str(e)[:ERROR_MSG_MAX_CHARS]}"
                print(f"  [ERROR] {e}")

            results.append(record)

    return results


# =========================
# MAIN
# =========================

FIELDNAMES = [
    "filename",
    "parser_config",
    "pages",
    "parse_time_s",
    "time_per_page",
    "word_count",
    "char_count",
    "num_documents",
    "has_doi",
    "has_abstract",
    "has_references",
    "has_title",
    "has_authors",
    "metadata_score",
    "status",
]


def _load_allowed_filenames_for_doc_type(doc_type: str) -> set[str]:
    if not GROUND_TRUTH_FILE.exists():
        raise FileNotFoundError(f"Ground truth file not found: {GROUND_TRUTH_FILE}")

    with open(GROUND_TRUTH_FILE, encoding="utf-8") as f:
        gt = json.load(f).get("documents", {})

    allowed = {
        filename
        for filename, record in gt.items()
        if record.get("doc_type") == doc_type
    }
    if not allowed:
        raise ValueError(f"No filenames found for doc_type='{doc_type}' in {GROUND_TRUTH_FILE}")
    return allowed


def _load_doc_type_map() -> dict[str, str]:
    if not GROUND_TRUTH_FILE.exists():
        return {}

    with open(GROUND_TRUTH_FILE, encoding="utf-8") as f:
        gt = json.load(f).get("documents", {})

    return {
        filename: record.get("doc_type", "")
        for filename, record in gt.items()
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run parsing benchmarks across parser configs and input variants."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="raw",
        choices=["raw", "preprocessed", "column", "all"],
        help="Primary dataset mode (default: raw).",
    )
    parser.add_argument(
        "--preprocessed",
        action="store_true",
        help="Also run preprocessed dataset benchmark.",
    )
    parser.add_argument(
        "--column",
        action="store_true",
        help="Also run column-linearized dataset benchmark.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache and force re-extraction.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(CONFIG_PROFILES.keys()),
        default="fast",
        help="Parser-config profile to run (default: fast).",
    )
    parser.add_argument(
        "--configs",
        default=None,
        help="Comma-separated config names to run (overrides --profile).",
    )
    parser.add_argument(
        "--doc-type",
        default=None,
        help="Optional doc_type filter from ground_truth.json (e.g. scientific_paper).",
    )
    parser.add_argument(
        "--docling-validate-bboxes",
        action="store_true",
        help="Drop Docling text blocks whose bbox contains no real PDF words (ghost-box mitigation).",
    )
    parsed = parser.parse_args()

    skip_existing = not parsed.no_cache
    run_raw = parsed.mode in ("raw", "all")
    run_preprocessed = parsed.mode in ("preprocessed", "all") or parsed.preprocessed
    run_column = parsed.mode in ("column", "all") or parsed.column

    if parsed.configs:
        selected_configs = [c.strip() for c in parsed.configs.split(",") if c.strip()]
    else:
        selected_configs = CONFIG_PROFILES[parsed.profile]
    allowed_filenames: set[str] | None = None
    if parsed.doc_type:
        allowed_filenames = _load_allowed_filenames_for_doc_type(parsed.doc_type)

    unknown_configs = [c for c in selected_configs if c not in CONFIGS]
    if unknown_configs:
        raise ValueError(f"Unknown config(s): {unknown_configs}")

    print(f"[INFO] Running parser configs ({len(selected_configs)}): {', '.join(selected_configs)}")
    if allowed_filenames is not None:
        print(f"[INFO] Filtering to doc_type='{parsed.doc_type}' ({len(allowed_filenames)} files)")
    if parsed.docling_validate_bboxes:
        print("[INFO] Docling ghost-box validation is ENABLED.")

    all_results = []

    if run_raw:
        all_results.extend(
            run_benchmark(
                INPUT_FOLDER_RAW,
                skip_existing=skip_existing,
                selected_configs=selected_configs,
                allowed_filenames=allowed_filenames,
                docling_validate_bboxes=parsed.docling_validate_bboxes,
            )
        )

    if run_preprocessed:
        all_results.extend(
            run_benchmark(
                INPUT_FOLDER_PREPROCESSED,
                config_suffix="_preprocessed",
                skip_existing=skip_existing,
                selected_configs=selected_configs,
                allowed_filenames=allowed_filenames,
                docling_validate_bboxes=parsed.docling_validate_bboxes,
            )
        )

    if run_column:
        all_results.extend(
            run_benchmark(
                INPUT_FOLDER_COLUMN,
                config_suffix="_column",
                skip_existing=skip_existing,
                selected_configs=selected_configs,
                allowed_filenames=allowed_filenames,
                docling_validate_bboxes=parsed.docling_validate_bboxes,
            )
        )

    # Write combined CSV
    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\nBenchmark complete → {len(all_results)} rows written to {OUTPUT_CSV}")
