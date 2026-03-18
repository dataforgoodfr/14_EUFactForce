"""
Fast single-document ranking utility for extracted parser outputs.

This script avoids the heavyweight global quality scoring run when you only need
to compare variants for one document.
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
from pathlib import Path

from eu_fact_force.exploration.parsing_benchmarking.benchmarking.extracted_text_store import (
    DATASET_VARIANTS,
)
from .scoring.similarity import score_reference_text
from eu_fact_force.exploration.parsing_benchmarking.scoring.utils import (
    find_reference_text_path,
    normalize_for_similarity,
    strip_footnotes_section,
    strip_references_section,
)

_PARSING_ROOT = Path(__file__).resolve().parent
DEFAULT_EXTRACTED_DIR = _PARSING_ROOT / "output" / "extracted_texts"
DEFAULT_GT_TEXT_DIR = _PARSING_ROOT / "ground_truth" / "texts"


def _prepare_fast(text: str) -> str:
    body = strip_references_section(text)
    body = strip_footnotes_section(body)
    return normalize_for_similarity(body)


def _fast_similarity(extracted: str, reference: str) -> float:
    return round(SequenceMatcher(None, _prepare_fast(reference), _prepare_fast(extracted)).ratio(), 4)


def _find_reference_file(gt_dir: Path, stem: str) -> Path:
    candidate = find_reference_text_path(stem=stem, gt_text_dir=gt_dir)
    if candidate is not None:
        return candidate
    raise FileNotFoundError(f"No ground-truth text found for '{stem}' in {gt_dir}")


def _collect_extracted_candidates(
    extracted_dir: Path,
    stem: str,
    parser_prefix: str,
) -> list[tuple[str, Path]]:
    """
    Collect candidates from structured layout.

    Returns tuples of (parser_config, file_path).
    """
    candidates: list[tuple[str, Path]] = []

    # Structured layout: <variant>/<config>/<stem>.txt
    for variant in DATASET_VARIANTS:
        variant_dir = extracted_dir / variant
        if not variant_dir.exists():
            continue
        for config_dir in sorted(p for p in variant_dir.iterdir() if p.is_dir()):
            config = config_dir.name
            if not config.startswith(parser_prefix):
                continue
            path = config_dir / f"{stem}.txt"
            if path.exists():
                candidates.append((config, path))

    dedup: dict[str, Path] = {}
    for config, path in candidates:
        dedup[config] = path
    return sorted(dedup.items(), key=lambda item: item[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank extracted outputs for a single document without running full quality scoring."
    )
    parser.add_argument(
        "document",
        help="Document stem or filename (e.g., BEUC-X-...pdf or BEUC-X-...).",
    )
    parser.add_argument(
        "--parser-prefix",
        default="docling",
        help="Only include configs that start with this prefix (default: docling).",
    )
    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="fast",
        help="fast: whole-text similarity only (quick). full: full fidelity metrics (slower).",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=DEFAULT_EXTRACTED_DIR,
        help="Directory containing extracted text files.",
    )
    parser.add_argument(
        "--gt-text-dir",
        type=Path,
        default=DEFAULT_GT_TEXT_DIR,
        help="Directory containing ground-truth reference texts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stem = Path(args.document).stem

    extracted_dir = args.extracted_dir.expanduser().resolve()
    gt_text_dir = args.gt_text_dir.expanduser().resolve()
    reference_file = _find_reference_file(gt_text_dir, stem)
    reference_text = reference_file.read_text(encoding="utf-8")

    candidates = _collect_extracted_candidates(
        extracted_dir=extracted_dir,
        stem=stem,
        parser_prefix=args.parser_prefix,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No extracted files found for stem='{stem}' and prefix='{args.parser_prefix}' in {extracted_dir}"
        )

    rows: list[dict] = []
    for config, path in candidates:
        extracted_text = path.read_text(encoding="utf-8")

        if args.mode == "fast":
            rows.append(
                {
                    "config": config,
                    "text_similarity": _fast_similarity(extracted_text, reference_text),
                    "char_count": len(extracted_text),
                }
            )
        else:
            metrics = score_reference_text(extracted_text, reference_file)
            rows.append({"config": config, **metrics, "char_count": len(extracted_text)})

    if args.mode == "fast":
        rows.sort(key=lambda x: (x["text_similarity"], -abs(x["char_count"])), reverse=True)
        print(f"Ranked {len(rows)} configs for {stem} ({args.parser_prefix}, mode=fast)")
        for idx, row in enumerate(rows, start=1):
            print(
                f"{idx:>2}. {row['config']:<45} "
                f"sim={row['text_similarity']:.4f} chars={row['char_count']}"
            )
        return

    rows.sort(
        key=lambda x: (
            x["text_similarity"],
            x["content_precision"],
            x["content_recall"],
            -1 if x["order_score"] is None else x["order_score"],
        ),
        reverse=True,
    )
    print(f"Ranked {len(rows)} configs for {stem} ({args.parser_prefix}, mode=full)")
    for idx, row in enumerate(rows, start=1):
        order_score = "None" if row["order_score"] is None else f"{row['order_score']:.4f}"
        print(
            f"{idx:>2}. {row['config']:<45} "
            f"sim={row['text_similarity']:.4f} "
            f"rec={row['content_recall']:.4f} "
            f"prec={row['content_precision']:.4f} "
            f"order={order_score} "
            f"chars={row['char_count']}"
        )


if __name__ == "__main__":
    main()
