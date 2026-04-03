"""Shared ground-truth loading helpers for parsing benchmarks."""

from __future__ import annotations

import json
from pathlib import Path

_PARSING_ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH_FILE = _PARSING_ROOT / "ground_truth" / "ground_truth.json"


def get_ground_truth_documents(ground_truth_file: Path = GROUND_TRUTH_FILE) -> dict[str, dict]:
    """Load ground-truth documents mapping from JSON."""
    if not ground_truth_file.exists():
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_file}")

    with open(ground_truth_file, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("documents", {})


def get_doc_type_map(ground_truth_file: Path = GROUND_TRUTH_FILE) -> dict[str, str]:
    """Return filename -> doc_type map, or empty map when file is missing."""
    if not ground_truth_file.exists():
        return {}
    documents = get_ground_truth_documents(ground_truth_file=ground_truth_file)
    return {
        filename: str(record.get("doc_type", ""))
        for filename, record in documents.items()
    }


def get_filenames_for_doc_type(
    doc_type: str,
    ground_truth_file: Path = GROUND_TRUTH_FILE,
) -> set[str]:
    """Return all filenames that belong to the requested doc_type."""
    documents = get_ground_truth_documents(ground_truth_file=ground_truth_file)
    allowed = {
        filename
        for filename, record in documents.items()
        if record.get("doc_type") == doc_type
    }
    if not allowed:
        raise ValueError(f"No filenames found for doc_type='{doc_type}' in {ground_truth_file}")
    return allowed


def filter_documents(
    documents: dict[str, dict],
    filename: str | None = None,
    doc_type: str | None = None,
) -> dict[str, dict]:
    """Apply filename/doc_type filters to loaded ground-truth documents."""
    filtered = documents
    if filename:
        if filename not in filtered:
            raise FileNotFoundError(f"Filename '{filename}' not found in ground_truth.json")
        filtered = {filename: filtered[filename]}

    if doc_type:
        filtered = {
            name: record
            for name, record in filtered.items()
            if record.get("doc_type") == doc_type
        }
        if not filtered:
            raise ValueError(f"No documents found for doc_type='{doc_type}'")
    return filtered

