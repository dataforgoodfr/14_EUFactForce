"""Helpers for storing and resolving extracted text files."""

from __future__ import annotations

from pathlib import Path

EXTRACTED_TEXT_DIR = Path("output/extracted_texts")
RAW_DATASET_VARIANT = "raw"


def structured_path(stem: str, config_name: str, dataset_variant: str) -> Path:
    """Return the canonical structured output path."""
    return EXTRACTED_TEXT_DIR / dataset_variant / config_name / f"{stem}.txt"


def resolve_existing_path(
    stem: str,
    config_name: str,
) -> Path | None:
    """Resolve extracted text path from canonical raw structured layout."""
    path = structured_path(
        stem=stem,
        config_name=config_name,
        dataset_variant=RAW_DATASET_VARIANT,
    )
    if path.exists():
        return path

    return None

