"""Helpers for storing and resolving extracted text files."""

from __future__ import annotations

from pathlib import Path

EXTRACTED_TEXT_DIR = Path("output/extracted_texts")
DATASET_VARIANTS = ("raw",)


def dataset_variant_from_suffix(config_suffix: str) -> str:
    """Map benchmark config suffix to dataset variant."""
    _ = config_suffix
    return "raw"


def infer_variant_from_config(config_name: str) -> str:
    """Infer dataset variant from parser config name."""
    _ = config_name
    return "raw"


def _candidate_config_aliases(config_name: str) -> list[str]:
    candidates = [config_name]
    if "docling_markdown_indexing" in config_name:
        legacy = config_name.replace("docling_markdown_indexing", "docling_postprocess_markdown")
        candidates.append(legacy)
    return list(dict.fromkeys(candidates))


def structured_path(stem: str, config_name: str, dataset_variant: str) -> Path:
    """Return the canonical structured output path."""
    return EXTRACTED_TEXT_DIR / dataset_variant / config_name / f"{stem}.txt"


def resolve_existing_path(
    stem: str,
    config_name: str,
    preferred_variant: str | None = None,
) -> Path | None:
    """
    Resolve extracted text path from structured layout.

    Search order:
      1) raw variant in structured layout
    """
    _ = preferred_variant
    variants = ["raw"]

    for alias in _candidate_config_aliases(config_name):
        for variant in variants:
            path = structured_path(stem=stem, config_name=alias, dataset_variant=variant)
            if path.exists():
                return path

    return None

