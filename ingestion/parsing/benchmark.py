import os
import re
import sys
import time
import csv
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from llama_index.core import SimpleDirectoryReader
from llama_index.readers.llama_parse import LlamaParse
import fitz  # PyMuPDF
from text_cleaning import postprocess_text

# =========================
# CONFIGURATION
# =========================
INPUT_FOLDER = "data/document_diversity"
INPUT_FOLDER_CLEAN = "data/document_diversity_clean"
INPUT_FOLDER_COLUMN = "data/document_diversity_column"
OUTPUT_CSV = "output/benchmark_results_extended.csv"
EXTRACTED_TEXT_DIR = "output/extracted_texts"
LLAMAPARSE_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

# Heuristic thresholds for metadata detection
MIN_TITLE_LENGTH = 10
MAX_TITLE_LENGTH = 300
TITLE_SCAN_LINES = 10
AUTHOR_CHUNK_CHARS = 2000
FIRST_CHUNK_CHARS = 5000
ERROR_MSG_MAX_CHARS = 200

# Parser configurations to benchmark
CONFIGS = {
    "llamaparse_text": {"type": "llamaparse", "result_type": "text"},
    "llamaparse_markdown": {"type": "llamaparse", "result_type": "markdown"},
    "pymupdf": {"type": "pymupdf"},
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


# =========================
# BENCHMARK FUNCTION
# =========================

def run_benchmark(
    input_folder: str,
    config_suffix: str = "",
    skip_existing: bool = False,
) -> list[dict]:
    """
    Run all parser configurations on PDFs in *input_folder*.

    If *config_suffix* is provided (e.g. '_clean'), it is appended to each
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
    if not files:
        print(f"[WARN] No PDF files in {input_folder} — skipping.")
        return []

    Path(EXTRACTED_TEXT_DIR).mkdir(exist_ok=True)
    results = []

    label = f" ({config_suffix.strip('_')})" if config_suffix else ""
    print(f"\n{'='*60}")
    print(f"Benchmarking {len(files)} PDFs from {input_folder}/{label}")
    print(f"{'='*60}\n")

    for file_path in files:
        for config_name, config in CONFIGS.items():
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
                full_text = postprocess_text(full_text)
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

if __name__ == "__main__":
    # Determine which folders to benchmark
    # Usage: python benchmark.py [original|clean|both] [--no-cache]
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    skip_existing = "--no-cache" not in sys.argv

    all_results = []

    if mode in ("original", "both"):
        all_results.extend(run_benchmark(INPUT_FOLDER, skip_existing=skip_existing))

    if mode in ("clean", "both", "all"):
        all_results.extend(
            run_benchmark(INPUT_FOLDER_CLEAN, config_suffix="_clean", skip_existing=skip_existing)
        )

    if mode in ("column", "all"):
        all_results.extend(
            run_benchmark(INPUT_FOLDER_COLUMN, config_suffix="_column", skip_existing=skip_existing)
        )

    # Write combined CSV
    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\nBenchmark complete → {len(all_results)} rows written to {OUTPUT_CSV}")
