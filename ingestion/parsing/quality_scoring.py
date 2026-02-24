"""
Quality scoring orchestrator for the LlamaParse benchmark.

Reads extracted texts from output/extracted_texts/ and compares them against
ground truth files to produce quality scores per (file, parser_config).
Ground-truth text normalization conventions are defined in
ground_truth/README.md.

Scores four complementary dimensions:
  1. Content presence (applicability-aware): title, authors, DOI, abstract, references, key_passage
  2. Structural quality (0-100): fragmentation, section order, duplicates
  3. Metadata accuracy (0-100): title, authors, DOI, date, source, abstract, keywords
  4. Reference-text similarity: text_similarity, content_recall, content_precision, order_score

Output: output/quality_scores.csv
"""

import json
import csv
import argparse
import time
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
from scoring.utils import FOUND, NOT_APPLICABLE

# =========================
# CONFIGURATION
# =========================
EXTRACTED_TEXT_DIR = Path("output/extracted_texts")
GROUND_TRUTH_FILE = Path("ground_truth/ground_truth.json")
GROUND_TRUTH_TEXT_DIR = Path("ground_truth/texts")
OUTPUT_CSV = "output/quality_scores.csv"
LEADERBOARD_CSV = "output/fidelity_leaderboard.csv"
DOC_TYPE_LEADERBOARD_CSV = "output/fidelity_leaderboard_by_doc_type.csv"
COMPOSITE_VERSION = "v1_0_35_25_25_15"

MISSING_FILE = "missing_file"

DEFAULT_PARSER_CONFIGS = [
    "llamaparse_text", "llamaparse_markdown", "pymupdf",
    "llamaparse_text_clean", "llamaparse_markdown_clean", "pymupdf_clean",
    "llamaparse_text_column", "llamaparse_markdown_column", "pymupdf_column",
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
    "quality_score_max": 0,
    "quality_score_pct": None,
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
    "fidelity_composite": None,
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
    references_found = score_references(full_text, gt.get("has_references"))
    key_passage_found, key_passage_ratio = score_key_passage(
        full_text, gt["key_passage"]
    )

    presence_results = [
        title_found, authors_found, doi_found,
        abstract_found, references_found, key_passage_found,
    ]
    applicable = [v for v in presence_results if v != NOT_APPLICABLE]
    quality_score = sum(v == FOUND for v in applicable)
    quality_score_max = len(applicable)
    quality_score_pct = (
        round((quality_score / quality_score_max) * 100, 1) if quality_score_max else None
    )

    return {
        "title_found": title_found, "title_ratio": title_ratio,
        "authors_found": authors_found, "authors_ratio": authors_ratio,
        "doi_found": doi_found,
        "abstract_found": abstract_found, "abstract_ratio": abstract_ratio,
        "references_found": references_found,
        "key_passage_found": key_passage_found, "key_passage_ratio": key_passage_ratio,
        "quality_score": quality_score,
        "quality_score_max": quality_score_max,
        "quality_score_pct": quality_score_pct,
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

def _discover_parser_configs(gt_docs: dict[str, dict]) -> list[str]:
    """Discover parser configs from extracted text filenames for GT docs."""
    discovered: set[str] = set()
    for filename in gt_docs:
        stem = Path(filename).stem
        for path in EXTRACTED_TEXT_DIR.glob(f"{stem}__*.txt"):
            if "__" in path.stem:
                discovered.add(path.stem.split("__", 1)[1])
    if not discovered:
        return list(DEFAULT_PARSER_CONFIGS)
    return sorted(discovered)


def _filter_docs(gt_docs: dict[str, dict], selected_docs: list[str] | None) -> dict[str, dict]:
    """Filter GT docs by filename or stem when selected_docs is provided."""
    if not selected_docs:
        return gt_docs
    selected = {s.strip() for s in selected_docs if s.strip()}
    out = {}
    for filename, gt in gt_docs.items():
        stem = Path(filename).stem
        if filename in selected or stem in selected:
            out[filename] = gt
    return out


def main(
    parser_configs: list[str],
    discover_configs: bool = False,
    selected_docs: list[str] | None = None,
    progress_every: int = 10,
):
    with open(GROUND_TRUTH_FILE, encoding="utf-8") as f:
        ground_truth = json.load(f)

    gt_docs = _filter_docs(ground_truth["documents"], selected_docs)
    print(f"[INFO] Loaded ground truth for {len(gt_docs)} selected documents.")
    if discover_configs:
        parser_configs = _discover_parser_configs(gt_docs)
        print(f"[INFO] Discovered parser configs from extracted text files: {parser_configs}")

    total_pairs = len(gt_docs) * len(parser_configs)
    print(f"[INFO] Planned scoring pairs: {total_pairs}")

    results = []
    processed_pairs = 0

    for filename, gt in gt_docs.items():
        print(f"[DOC] {filename}")
        for config in parser_configs:
            pair_start = time.perf_counter()
            text_file = EXTRACTED_TEXT_DIR / f"{Path(filename).stem}__{config}.txt"
            record = _empty_record(filename, config, gt["doc_type"])

            if not text_file.exists():
                print(f"  [SKIP] {config} — {text_file} not found")
                results.append(record)
                processed_pairs += 1
                if processed_pairs % max(1, progress_every) == 0:
                    print(f"[PROGRESS] {processed_pairs}/{total_pairs} pairs processed")
                continue

            full_text = text_file.read_text(encoding="utf-8")
            print(f"  [CONFIG] {config} ({len(full_text)} chars)")

            record.update(_score_content_presence(full_text, gt))
            record.update(_score_structural(full_text, gt))

            if _has_metadata_annotations(gt):
                record.update(_score_metadata(full_text, gt))

            ref_path = _find_reference_text(filename)
            if ref_path is not None:
                record.update(score_reference_text(full_text, ref_path))

            results.append(record)
            processed_pairs += 1
            elapsed = time.perf_counter() - pair_start
            print(f"  [DONE] {config} in {elapsed:.2f}s")
            if processed_pairs % max(1, progress_every) == 0:
                print(f"[PROGRESS] {processed_pairs}/{total_pairs} pairs processed")

    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nQuality scoring complete → {len(results)} rows written to {OUTPUT_CSV}")
    _write_leaderboards(results)
    _print_summaries(results, parser_configs)


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


def _print_summaries(results: list[dict], parser_configs: list[str]):
    """Print per-config summary tables to stdout."""
    _print_fidelity_summary(results, parser_configs)
    _print_content_presence_summary(results, parser_configs)
    _print_structural_summary(results, parser_configs)
    _print_similarity_summary(results, parser_configs)
    _print_metadata_summary(results, parser_configs)


def _print_fidelity_summary(results: list[dict], parser_configs: list[str]):
    if not any(r.get("fidelity_composite") is not None for r in results):
        return
    print(f"\n=== Fidelity Composite Summary ({COMPOSITE_VERSION}) ===")
    for config in parser_configs:
        rows = _rows_for(results, config, "fidelity_composite")
        if rows:
            print(
                f"  {config}: composite={_avg(rows, 'fidelity_composite'):.3f}"
                f"  sim={_avg(rows, 'text_similarity'):.3f}"
                f"  recall={_avg(rows, 'content_recall'):.3f}"
                f"  precision={_avg(rows, 'content_precision'):.3f}"
            )


def _print_content_presence_summary(results: list[dict], parser_configs: list[str]):
    print("\n=== Content Presence Summary ===")
    for config in parser_configs:
        rows = _rows_for(results, config, "quality_score_max")
        if not rows:
            continue

        # Only keep rows where score is meaningful for this document
        valid_rows = [r for r in rows if r.get("quality_score_max", 0) > 0]
        if not valid_rows:
            continue

        avg_raw = sum(r["quality_score"] for r in valid_rows) / len(valid_rows)
        avg_max = sum(r["quality_score_max"] for r in valid_rows) / len(valid_rows)
        avg_pct = _avg(valid_rows, "quality_score_pct")
        print(
            f"  {config}: score={avg_raw:.2f}/{avg_max:.2f}"
            f"  pct={avg_pct:.1f}%"
        )


def _print_structural_summary(results: list[dict], parser_configs: list[str]):
    print("\n=== Structural Quality Summary ===")
    for config in parser_configs:
        rows = _rows_for(results, config, "structural_quality")
        if rows:
            print(f"  {config}: structural_quality={_avg(rows, 'structural_quality'):.1f}/100"
                  f"  frag={_avg(rows, 'fragmentation_ratio'):.3f}")


def _print_similarity_summary(results: list[dict], parser_configs: list[str]):
    if not any(r.get("text_similarity") is not None for r in results):
        return
    print("\n=== Reference-Text Similarity (documents with ground truth text) ===")
    for config in parser_configs:
        rows = _rows_for(results, config, "text_similarity")
        if rows:
            order = _avg(rows, "order_score")
            order_str = f"  order={order:.3f}" if order is not None else ""
            print(f"  {config}: similarity={_avg(rows, 'text_similarity'):.3f}"
                  f"  recall={_avg(rows, 'content_recall'):.3f}"
                  f"  precision={_avg(rows, 'content_precision'):.3f}{order_str}")


def _print_metadata_summary(results: list[dict], parser_configs: list[str]):
    if not any(r.get("meta_accuracy_score") is not None for r in results):
        return
    print("\n=== Metadata Accuracy Summary ===")
    for config in parser_configs:
        rows = _rows_for(results, config, "meta_accuracy_score")
        if rows:
            doi = _avg(rows, "meta_doi_accuracy")
            abstract = _avg(rows, "meta_abstract_accuracy")
            doi_str = f"  doi={doi:.3f}" if doi is not None else ""
            abs_str = f"  abstract={abstract:.3f}" if abstract is not None else ""
            print(f"  {config}: score={_avg(rows, 'meta_accuracy_score'):.1f}/100"
                  f"  title={_avg(rows, 'meta_title_accuracy'):.3f}"
                  f"  authors={_avg(rows, 'meta_authors_recall'):.3f}{doi_str}{abs_str}")


def _write_leaderboards(results: list[dict]):
    """
    Write aggregate fidelity leaderboards:
      - by parser_config
      - by (doc_type, parser_config)
    """
    def _round_opt(value: float | None) -> float | None:
        return round(value, 4) if value is not None else None

    by_config_rows = []
    parser_configs = sorted({r["parser_config"] for r in results if r.get("parser_config")})
    for config in parser_configs:
        rows = _rows_for(results, config, "fidelity_composite")
        if not rows:
            continue
        by_config_rows.append(
            {
                "parser_config": config,
                "num_documents": len(rows),
                "composite_version": COMPOSITE_VERSION,
                "fidelity_composite_avg": _round_opt(_avg(rows, "fidelity_composite")),
                "text_similarity_avg": _round_opt(_avg(rows, "text_similarity")),
                "content_recall_avg": _round_opt(_avg(rows, "content_recall")),
                "content_precision_avg": _round_opt(_avg(rows, "content_precision")),
                "order_score_avg": _round_opt(_avg(rows, "order_score")),
            }
        )

    by_config_rows.sort(key=lambda r: r["fidelity_composite_avg"], reverse=True)
    if by_config_rows:
        with open(LEADERBOARD_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(by_config_rows[0].keys()))
            writer.writeheader()
            writer.writerows(by_config_rows)

    doc_types = sorted({r["doc_type"] for r in results if r.get("doc_type")})
    by_type_rows = []
    for doc_type in doc_types:
        for config in parser_configs:
            rows = [
                r for r in results
                if r.get("doc_type") == doc_type
                and r.get("parser_config") == config
                and r.get("fidelity_composite") is not None
            ]
            if not rows:
                continue
            by_type_rows.append(
                {
                    "doc_type": doc_type,
                    "parser_config": config,
                    "num_documents": len(rows),
                    "composite_version": COMPOSITE_VERSION,
                    "fidelity_composite_avg": _round_opt(_avg(rows, "fidelity_composite")),
                    "text_similarity_avg": _round_opt(_avg(rows, "text_similarity")),
                    "content_recall_avg": _round_opt(_avg(rows, "content_recall")),
                    "content_precision_avg": _round_opt(_avg(rows, "content_precision")),
                    "order_score_avg": _round_opt(_avg(rows, "order_score")),
                }
            )
    by_type_rows.sort(key=lambda r: (r["doc_type"], -r["fidelity_composite_avg"]))
    if by_type_rows:
        with open(DOC_TYPE_LEADERBOARD_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(by_type_rows[0].keys()))
            writer.writeheader()
            writer.writerows(by_type_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quality scoring for parsing benchmark")
    parser.add_argument(
        "--discover-configs",
        action="store_true",
        help="Discover parser configs from output/extracted_texts for GT docs.",
    )
    parser.add_argument(
        "--configs",
        nargs="*",
        default=list(DEFAULT_PARSER_CONFIGS),
        help="Explicit parser config names to score (ignored if --discover-configs).",
    )
    parser.add_argument(
        "--docs",
        nargs="*",
        default=None,
        help="Optional subset of document filenames or stems to score.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N (doc,config) pairs.",
    )
    args = parser.parse_args()
    main(
        parser_configs=args.configs,
        discover_configs=args.discover_configs,
        selected_docs=args.docs,
        progress_every=args.progress_every,
    )
