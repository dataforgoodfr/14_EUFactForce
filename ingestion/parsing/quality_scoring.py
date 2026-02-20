"""
Quality scoring orchestrator for the LlamaParse benchmark.

Reads extracted texts from output/extracted_texts/ and compares them against
ground truth files to produce quality scores per (file, parser_config).

Scores four complementary dimensions:
  1. Content presence (0-6): title, authors, DOI, abstract, references, key_passage
  2. Structural quality (0-100): fragmentation, section order, duplicates
  3. Metadata accuracy (0-100): title, authors, DOI, date, source, abstract, keywords
  4. Reference-text similarity: text_similarity, content_recall, content_precision, order_score

Output: output/quality_scores.csv
"""

import json
import csv
from pathlib import Path

from scoring.content import (
    score_title, score_authors, score_doi, score_abstract,
    score_references, score_key_passage,
    score_fragmentation, score_section_order, score_duplicate_content,
    compute_structural_quality, score_continuity_passages,
)
from scoring.metadata import (
    score_title_accuracy, score_authors_accuracy, score_doi_accuracy,
    score_date_accuracy, score_source_accuracy, score_abstract_accuracy,
    score_keywords_accuracy, compute_metadata_accuracy_score,
)
from scoring.similarity import score_reference_text
from scoring.utils import FOUND

# =========================
# CONFIGURATION
# =========================
EXTRACTED_TEXT_DIR = Path("output/extracted_texts")
GROUND_TRUTH_FILE = Path("ground_truth/ground_truth.json")
GROUND_TRUTH_TEXT_DIR = Path("ground_truth/texts")
OUTPUT_CSV = "output/quality_scores.csv"

MISSING_FILE = "missing_file"

PARSER_CONFIGS = [
    "llamaparse_text", "llamaparse_markdown", "pymupdf",
    "llamaparse_text_clean", "llamaparse_markdown_clean", "pymupdf_clean",
    "llamaparse_text_column", "llamaparse_markdown_column", "pymupdf_column",
    "docling_text", "docling_markdown",
    "docling_text_clean", "docling_markdown_clean",
    "docling_text_column", "docling_markdown_column",
    "docling_postprocess_text", "docling_postprocess_markdown",
    "docling_postprocess_text_clean", "docling_postprocess_markdown_clean",
    "docling_postprocess_text_column", "docling_postprocess_markdown_column",
]

# Reference text file extensions, checked in priority order
REFERENCE_TEXT_EXTENSIONS = (".md", ".txt")

# Single source of truth for CSV columns and their missing-file defaults.
# _empty_record() and CSV_FIELDNAMES are both derived from this.
_FIELD_DEFAULTS: dict[str, str | float | int | None] = {
    "filename": "",
    "parser_config": "",
    "doc_type": "",
    # Content presence
    "title_found": MISSING_FILE, "title_ratio": 0.0,
    "authors_found": MISSING_FILE, "authors_ratio": 0.0,
    "doi_found": MISSING_FILE,
    "abstract_found": MISSING_FILE, "abstract_ratio": 0.0,
    "references_found": MISSING_FILE,
    "key_passage_found": MISSING_FILE, "key_passage_ratio": 0.0,
    "quality_score": 0,
    # Structural quality
    "fragmentation_ratio": None, "section_order_score": None,
    "duplicate_content_ratio": None, "structural_quality": None,
    # Continuity passages
    "continuity_found": None, "continuity_total": None, "continuity_avg_ratio": None,
    # Metadata accuracy
    "meta_title_accuracy": None, "meta_authors_recall": None,
    "meta_authors_avg_ratio": None, "meta_doi_accuracy": None,
    "meta_date_accuracy": None, "meta_source_accuracy": None,
    "meta_abstract_accuracy": None, "meta_keyword_recall": None,
    "meta_keyword_avg_ratio": None, "meta_accuracy_score": None,
    # Reference-text similarity
    "text_similarity": None, "content_recall": None,
    "content_precision": None, "order_score": None,
}

CSV_FIELDNAMES = list(_FIELD_DEFAULTS.keys())


# =========================
# SCORING HELPERS
# =========================

def _empty_record(filename: str, config: str, doc_type: str) -> dict:
    """Return a record with all fields set to their missing-file defaults."""
    record = dict(_FIELD_DEFAULTS)
    record["filename"] = filename
    record["parser_config"] = config
    record["doc_type"] = doc_type
    return record


def _score_content_presence(full_text: str, gt: dict) -> dict:
    """Score content-presence fields and return partial record update."""
    title_found, title_ratio = score_title(full_text, gt["title"])
    authors_found, authors_ratio = score_authors(full_text, gt["authors"])
    doi_found = score_doi(full_text, gt.get("doi"))
    abstract_found, abstract_ratio = score_abstract(
        full_text, gt.get("abstract_first_sentence")
    )
    references_found = score_references(full_text)
    key_passage_found, key_passage_ratio = score_key_passage(
        full_text, gt["key_passage"]
    )

    presence_results = [
        title_found, authors_found, doi_found,
        abstract_found, references_found, key_passage_found,
    ]
    quality_score = sum(v == FOUND for v in presence_results)

    return {
        "title_found": title_found, "title_ratio": title_ratio,
        "authors_found": authors_found, "authors_ratio": authors_ratio,
        "doi_found": doi_found,
        "abstract_found": abstract_found, "abstract_ratio": abstract_ratio,
        "references_found": references_found,
        "key_passage_found": key_passage_found, "key_passage_ratio": key_passage_ratio,
        "quality_score": quality_score,
    }


def _score_structural(full_text: str, gt: dict) -> dict:
    """Score structural quality and continuity, return partial record update."""
    fragmentation = score_fragmentation(full_text)
    section_order = score_section_order(full_text, gt.get("sections_in_order"))
    duplicate_ratio = score_duplicate_content(full_text)
    structural = compute_structural_quality(fragmentation, section_order, duplicate_ratio)

    cont_found, cont_total, cont_avg = score_continuity_passages(
        full_text, gt.get("continuity_passages")
    )
    has_continuity = cont_total > 0

    return {
        "fragmentation_ratio": fragmentation,
        "section_order_score": section_order,
        "duplicate_content_ratio": duplicate_ratio,
        "structural_quality": structural,
        "continuity_found": cont_found if has_continuity else None,
        "continuity_total": cont_total if has_continuity else None,
        "continuity_avg_ratio": cont_avg if has_continuity else None,
    }


def _score_metadata(full_text: str, gt_meta: dict) -> dict:
    """Score metadata accuracy and return partial record update."""
    m_title = score_title_accuracy(full_text, gt_meta["title"])
    m_auth_recall, m_auth_avg = score_authors_accuracy(full_text, gt_meta["authors"])
    m_doi = score_doi_accuracy(full_text, gt_meta.get("doi"))
    m_date = score_date_accuracy(full_text, gt_meta.get("publication_date"))
    m_source = score_source_accuracy(full_text, gt_meta.get("source"))
    m_abstract = score_abstract_accuracy(full_text, gt_meta.get("abstract_first_sentence"))
    m_kw_recall, m_kw_avg = score_keywords_accuracy(full_text, gt_meta.get("keywords"))
    m_overall = compute_metadata_accuracy_score(
        m_title, m_auth_recall, m_doi, m_date, m_source, m_abstract, m_kw_recall,
    )

    return {
        "meta_title_accuracy": m_title,
        "meta_authors_recall": m_auth_recall,
        "meta_authors_avg_ratio": m_auth_avg,
        "meta_doi_accuracy": m_doi,
        "meta_date_accuracy": m_date,
        "meta_source_accuracy": m_source,
        "meta_abstract_accuracy": m_abstract,
        "meta_keyword_recall": m_kw_recall,
        "meta_keyword_avg_ratio": m_kw_avg,
        "meta_accuracy_score": m_overall,
    }


def _has_metadata_annotations(gt: dict) -> bool:
    """Check if this ground truth entry has extended metadata annotations.

    All entries have title and authors.  publication_date, source, and
    keywords are only annotated for documents where metadata scoring is
    meaningful, so their presence signals that the entry is metadata-ready.
    """
    return gt.get("publication_date") is not None or gt.get("source") is not None


def _find_reference_text(filename: str) -> Path | None:
    """Find a ground truth reference text file for the given document."""
    stem = Path(filename).stem
    for ext in REFERENCE_TEXT_EXTENSIONS:
        candidate = GROUND_TRUTH_TEXT_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


# =========================
# MAIN
# =========================

def main():
    with open(GROUND_TRUTH_FILE, encoding="utf-8") as f:
        ground_truth = json.load(f)

    gt_docs = ground_truth["documents"]
    print(f"[INFO] Loaded ground truth for {len(gt_docs)} documents.")
    results = []

    for filename, gt in gt_docs.items():
        for config in PARSER_CONFIGS:
            text_file = EXTRACTED_TEXT_DIR / f"{Path(filename).stem}__{config}.txt"
            record = _empty_record(filename, config, gt["doc_type"])

            if not text_file.exists():
                print(f"  [SKIP] {text_file} not found")
                results.append(record)
                continue

            full_text = text_file.read_text(encoding="utf-8")
            print(f"[{config}] Scoring {filename} ({len(full_text)} chars) ...")

            record.update(_score_content_presence(full_text, gt))
            record.update(_score_structural(full_text, gt))

            if _has_metadata_annotations(gt):
                record.update(_score_metadata(full_text, gt))

            ref_path = _find_reference_text(filename)
            if ref_path is not None:
                record.update(score_reference_text(full_text, ref_path))

            results.append(record)

    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nQuality scoring complete → {len(results)} rows written to {OUTPUT_CSV}")
    _print_summaries(results)


# =========================
# SUMMARY OUTPUT
# =========================

def _avg(rows: list[dict], field: str) -> float | None:
    """Average of *field* across rows, skipping None values."""
    valid = [r[field] for r in rows if r.get(field) is not None]
    return sum(valid) / len(valid) if valid else None


def _rows_for(results: list[dict], config: str, require: str) -> list[dict]:
    """Filter results for a config where *require* field is not None."""
    return [
        r for r in results
        if r["parser_config"] == config and r.get(require) is not None
    ]


def _print_summaries(results: list[dict]):
    """Print per-config summary tables to stdout."""
    _print_structural_summary(results)
    _print_similarity_summary(results)
    _print_metadata_summary(results)


def _print_structural_summary(results: list[dict]):
    print("\n=== Structural Quality Summary ===")
    for config in PARSER_CONFIGS:
        rows = _rows_for(results, config, "structural_quality")
        if rows:
            print(f"  {config}: structural_quality={_avg(rows, 'structural_quality'):.1f}/100"
                  f"  frag={_avg(rows, 'fragmentation_ratio'):.3f}")


def _print_similarity_summary(results: list[dict]):
    if not any(r.get("text_similarity") is not None for r in results):
        return
    print("\n=== Reference-Text Similarity (documents with ground truth text) ===")
    for config in PARSER_CONFIGS:
        rows = _rows_for(results, config, "text_similarity")
        if rows:
            order = _avg(rows, "order_score")
            order_str = f"  order={order:.3f}" if order is not None else ""
            print(f"  {config}: similarity={_avg(rows, 'text_similarity'):.3f}"
                  f"  recall={_avg(rows, 'content_recall'):.3f}"
                  f"  precision={_avg(rows, 'content_precision'):.3f}{order_str}")


def _print_metadata_summary(results: list[dict]):
    if not any(r.get("meta_accuracy_score") is not None for r in results):
        return
    print("\n=== Metadata Accuracy Summary ===")
    for config in PARSER_CONFIGS:
        rows = _rows_for(results, config, "meta_accuracy_score")
        if rows:
            doi = _avg(rows, "meta_doi_accuracy")
            abstract = _avg(rows, "meta_abstract_accuracy")
            doi_str = f"  doi={doi:.3f}" if doi is not None else ""
            abs_str = f"  abstract={abstract:.3f}" if abstract is not None else ""
            print(f"  {config}: score={_avg(rows, 'meta_accuracy_score'):.1f}/100"
                  f"  title={_avg(rows, 'meta_title_accuracy'):.3f}"
                  f"  authors={_avg(rows, 'meta_authors_recall'):.3f}{doi_str}{abs_str}")


if __name__ == "__main__":
    main()
