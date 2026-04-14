import os
import time
import csv
import argparse
from pathlib import Path

import fitz as PyMuPDF
from dotenv import load_dotenv
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.benchmark_metadata import (
    compute_metadata_score,
    detect_abstract,
    detect_authors,
    detect_doi,
    detect_references,
    detect_title,
)
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.parsers import (
    parse_with_config,
)
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.extracted_text_store import (
    RAW_DATASET_VARIANT,
    resolve_existing_path,
    structured_path,
)
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.ground_truth_loader import (
    get_doc_type_map,
    get_filenames_for_doc_type,
)
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.parser_config import (
    CONFIGS,
    CONFIG_PROFILES,
    deduplicate_parser_config_names,
)
from eu_fact_force.ingestion.parsing.text_cleaning import postprocess_text

load_dotenv()

# =========================
# CONFIGURATION
# =========================
_PARSING_ROOT = Path(__file__).resolve().parent
INPUT_FOLDER_RAW = _PARSING_ROOT / "data" / "document_diversity"
OUTPUT_CSV = _PARSING_ROOT / "output" / "benchmark_results_extended.csv"
LLAMAPARSE_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
FIRST_CHUNK_CHARS = 5000
ERROR_MSG_MAX_CHARS = 200


# =========================
# BENCHMARK FUNCTION
# =========================

def run_benchmark(
    input_folder: str,
    skip_existing: bool = False,
    selected_configs: list[str] | None = None,
    allowed_filenames: set[str] | None = None,
    docling_validate_bboxes: bool = False,
) -> list[dict]:
    """
    Run all parser configurations on PDFs in *input_folder*.

    If *skip_existing* is True, skip any (file, config) combination whose
    extracted-text file already exists, and reconstruct the record from it.

    Returns a list of result records.
    """
    input_path = Path(input_folder)
    files = _collect_input_files(input_path=input_path, allowed_filenames=allowed_filenames)
    if not files:
        return []

    dataset_variant = RAW_DATASET_VARIANT
    _print_benchmark_header(input_folder=input_folder, file_count=len(files))

    results: list[dict] = []
    active_config_names = selected_configs if selected_configs is not None else list(CONFIGS.keys())
    doc_type_map = get_doc_type_map()

    for file_path in files:
        file_doc_type = doc_type_map.get(file_path.name)
        for config_name in active_config_names:
            results.append(
                _run_file_config_benchmark(
                    file_path=file_path,
                    config_name=config_name,
                    dataset_variant=dataset_variant,
                    skip_existing=skip_existing,
                    file_doc_type=file_doc_type,
                    docling_validate_bboxes=docling_validate_bboxes,
                )
            )

    return results


def _collect_input_files(input_path: Path, allowed_filenames: set[str] | None) -> list[Path]:
    if not input_path.exists():
        print(f"[WARN] Input folder {input_path} not found — skipping.")
        return []

    files = sorted(f for f in input_path.iterdir() if f.suffix.lower() == ".pdf")
    if allowed_filenames is not None:
        files = [f for f in files if f.name in allowed_filenames]
    if not files:
        print(f"[WARN] No PDF files in {input_path} — skipping.")
    return files


def _print_benchmark_header(input_folder: str, file_count: int) -> None:
    print(f"\n{'='*60}")
    print(f"Benchmarking {file_count} PDFs from {input_folder}")
    print(f"{'='*60}\n")


def _estimate_pdf_pages(file_path: Path) -> int:
    try:
        with PyMuPDF.open(str(file_path)) as doc:
            return len(doc)
    except Exception:
        return 1


def _new_error_record(filename: str, parser_config_name: str) -> dict:
    return {
        "filename": filename,
        "parser_config": parser_config_name,
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


def _build_record_from_extracted_text(
    *,
    file_path: Path,
    parser_config_name: str,
    full_text: str,
    pages: int,
    parse_time_s: float | None,
    num_docs: int | None,
    status: str,
) -> dict:
    first_chunk = full_text[:FIRST_CHUNK_CHARS]
    record = {
        "filename": file_path.name,
        "parser_config": parser_config_name,
        "pages": pages,
        "parse_time_s": round(parse_time_s, 2) if parse_time_s is not None else None,
        "time_per_page": round(parse_time_s / pages, 3) if parse_time_s and pages else None,
        "word_count": len(full_text.split()),
        "char_count": len(full_text),
        "num_documents": num_docs,
        "has_doi": detect_doi(full_text),
        "has_abstract": detect_abstract(full_text),
        "has_references": detect_references(full_text),
        "has_title": detect_title(first_chunk),
        "has_authors": detect_authors(first_chunk),
        "metadata_score": 0,
        "status": status,
    }
    record["metadata_score"] = compute_metadata_score(record)
    return record


def _build_cached_record(file_path: Path, output_config_name: str, out_file: Path) -> dict:
    full_text = out_file.read_text(encoding="utf-8")
    pages = _estimate_pdf_pages(file_path)
    return _build_record_from_extracted_text(
        file_path=file_path,
        parser_config_name=output_config_name,
        full_text=full_text,
        pages=pages,
        parse_time_s=None,
        num_docs=None,
        status="success (cached)",
    )


def _resolve_output_paths(
    *,
    file_path: Path,
    config_name: str,
    dataset_variant: str,
) -> tuple[str, Path]:
    """Build output config label and canonical output path."""
    output_config_name = config_name
    out_file = structured_path(
        stem=file_path.stem,
        config_name=output_config_name,
        dataset_variant=dataset_variant,
    )
    return output_config_name, out_file


def _resolve_cache_file(
    *,
    skip_existing: bool,
    file_path: Path,
    output_config_name: str,
    dataset_variant: str,
) -> Path | None:
    """Resolve cached extracted-text file when cache mode is enabled."""
    if not skip_existing:
        return None
    return resolve_existing_path(
        stem=file_path.stem,
        config_name=output_config_name,
    )


def _persist_parse_outputs(*, out_file: Path, raw_text: str, full_text: str) -> None:
    """Write canonical, raw, and processed extraction snapshots."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.with_suffix(".raw.txt").write_text(raw_text, encoding="utf-8")
    out_file.with_suffix(".processed.txt").write_text(full_text, encoding="utf-8")
    out_file.write_text(full_text, encoding="utf-8")


def _run_file_config_benchmark(
    *,
    file_path: Path,
    config_name: str,
    dataset_variant: str,
    skip_existing: bool,
    file_doc_type: str | None,
    docling_validate_bboxes: bool,
) -> dict:
    """Run one file/config benchmark unit (cached or fresh parse)."""
    output_config_name, out_file = _resolve_output_paths(
        file_path=file_path,
        config_name=config_name,
        dataset_variant=dataset_variant,
    )
    cache_file = _resolve_cache_file(
        skip_existing=skip_existing,
        file_path=file_path,
        output_config_name=output_config_name,
        dataset_variant=dataset_variant,
    )
    if cache_file is not None:
        print(f"[{output_config_name}] {file_path.name} — cached ✓")
        return _build_cached_record(
            file_path=file_path,
            output_config_name=output_config_name,
            out_file=cache_file,
        )

    print(f"[{output_config_name}] Processing {file_path.name} ...")
    return _run_single_parse(
        file_path=file_path,
        output_config_name=output_config_name,
        config=CONFIGS[config_name],
        out_file=out_file,
        file_doc_type=file_doc_type,
        docling_validate_bboxes=docling_validate_bboxes,
    )


def _run_single_parse(
    *,
    file_path: Path,
    output_config_name: str,
    config: dict[str, object],
    out_file: Path,
    file_doc_type: str | None,
    docling_validate_bboxes: bool,
) -> dict:
    record = _new_error_record(filename=file_path.name, parser_config_name=output_config_name)
    try:
        start = time.perf_counter()
        raw_text, pages, num_docs = parse_with_config(
            file_path=file_path,
            config=config,
            docling_validate_bboxes=docling_validate_bboxes,
            llamaparse_api_key=LLAMAPARSE_API_KEY,
        )
        parse_time = time.perf_counter() - start

        # Keep side-by-side snapshots for default diffability:
        # - <stem>.raw.txt: parser output before shared postprocessing
        # - <stem>.processed.txt: output after shared postprocessing
        full_text = postprocess_text(
            raw_text,
            doc_type=file_doc_type,
            indexing_cleanup=bool(config.get("indexing_cleanup", False)),
        )
        _persist_parse_outputs(out_file=out_file, raw_text=raw_text, full_text=full_text)

        record = _build_record_from_extracted_text(
            file_path=file_path,
            parser_config_name=output_config_name,
            full_text=full_text,
            pages=pages,
            parse_time_s=parse_time,
            num_docs=num_docs,
            status="success",
        )
    except Exception as e:
        record["status"] = f"error: {str(e)[:ERROR_MSG_MAX_CHARS]}"
        print(f"  [ERROR] {e}")
    return record


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

def _parse_args() -> argparse.Namespace:
    """Parse benchmark CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run parsing benchmarks across parser configs on raw PDFs."
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
    return parser.parse_args()


def _resolve_selected_configs(parsed: argparse.Namespace) -> list[str]:
    """Resolve selected parser configs from explicit list or profile."""
    if not parsed.configs:
        return CONFIG_PROFILES[parsed.profile]
    return deduplicate_parser_config_names(
        [c.strip() for c in parsed.configs.split(",") if c.strip()]
    )


def _validate_selected_configs(selected_configs: list[str]) -> None:
    """Validate requested config names against registry."""
    unknown_configs = [c for c in selected_configs if c not in CONFIGS]
    if unknown_configs:
        raise ValueError(f"Unknown config(s): {unknown_configs}")


def _print_run_context(
    *,
    selected_configs: list[str],
    doc_type: str | None,
    allowed_filenames: set[str] | None,
    docling_validate_bboxes: bool,
) -> None:
    """Print top-level benchmark execution context."""
    print(f"[INFO] Running parser configs ({len(selected_configs)}): {', '.join(selected_configs)}")
    if allowed_filenames is not None:
        print(f"[INFO] Filtering to doc_type='{doc_type}' ({len(allowed_filenames)} files)")
    if docling_validate_bboxes:
        print("[INFO] Docling ghost-box validation is ENABLED.")


def _run_enabled_benchmarks(
    *,
    input_folder: str,
    skip_existing: bool,
    selected_configs: list[str],
    allowed_filenames: set[str] | None,
    docling_validate_bboxes: bool,
) -> list[dict]:
    """Execute benchmark on the configured raw dataset."""
    return run_benchmark(
        input_folder=input_folder,
        skip_existing=skip_existing,
        selected_configs=selected_configs,
        allowed_filenames=allowed_filenames,
        docling_validate_bboxes=docling_validate_bboxes,
    )


def _write_results_csv(results: list[dict]) -> None:
    """Write benchmark records to the output CSV."""
    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    """CLI entrypoint for running parsing benchmarks."""
    parsed = _parse_args()
    skip_existing = not parsed.no_cache
    selected_configs = _resolve_selected_configs(parsed)
    _validate_selected_configs(selected_configs)

    allowed_filenames: set[str] | None = None
    if parsed.doc_type:
        allowed_filenames = get_filenames_for_doc_type(parsed.doc_type)
    _print_run_context(
        selected_configs=selected_configs,
        doc_type=parsed.doc_type,
        allowed_filenames=allowed_filenames,
        docling_validate_bboxes=parsed.docling_validate_bboxes,
    )
    all_results = _run_enabled_benchmarks(
        input_folder=INPUT_FOLDER_RAW,
        skip_existing=skip_existing,
        selected_configs=selected_configs,
        allowed_filenames=allowed_filenames,
        docling_validate_bboxes=parsed.docling_validate_bboxes,
    )
    _write_results_csv(all_results)

    print(f"\nBenchmark complete → {len(all_results)} rows written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
