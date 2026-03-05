"""Data loading and ground-truth validation for embedding benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .benchmark_config import (
    CHUNK_LABEL_TO_GAIN,
    EXTRACTED_TEXTS_DIR,
    GROUND_TRUTH_PATH,
    VALID_CHUNKING_STRATEGIES,
)


def _error_suffix(idx: int, strategy: str | None = None, row_idx: int | None = None) -> str:
    parts = [f"index {idx}"]
    if strategy:
        parts.append(f"strategy {strategy}")
    if row_idx is not None:
        parts.append(f"row {row_idx}")
    return f" ({', '.join(parts)})."


def _require_dict(value: object, field_name: str, idx: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object (index {idx}).")
    return value


def _require_list(value: object, field_name: str, idx: int, strategy: str | None = None) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list{_error_suffix(idx, strategy=strategy)}")
    return value


def _validate_strategy_name(strategy: str, field_name: str, idx: int) -> None:
    if strategy not in VALID_CHUNKING_STRATEGIES:
        raise ValueError(f"Unsupported strategy '{strategy}' in {field_name} (index {idx}).")


def _require_keys(
    row: dict, required_keys: set[str], field_name: str, idx: int, strategy: str | None, row_idx: int
) -> None:
    if required_keys - set(row.keys()):
        keys = ", ".join(sorted(required_keys))
        raise ValueError(
            f"Each {field_name} row must contain {keys}"
            f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
        )


def load_documents() -> dict[str, str]:
    """Load the LlamaParse markdown extractions (base variant, no clean/column)."""
    docs: dict[str, str] = {}
    for path in sorted(EXTRACTED_TEXTS_DIR.glob("*__llamaparse_markdown.txt")):
        doc_id = path.stem.replace("__llamaparse_markdown", "")
        text = path.read_text(encoding="utf-8").strip()
        if text:
            docs[doc_id] = text

    print(f"Loaded {len(docs)} documents:")
    for doc_id in docs:
        print(f"  - {doc_id} ({len(docs[doc_id]):,} chars)")
    return docs


def _validate_chunk_labels(
    rows: object, idx: int, field_name: str, strategy: str | None = None
) -> None:
    for row_idx, row in enumerate(_require_list(rows, field_name, idx, strategy=strategy)):
        if not isinstance(row, dict):
            raise ValueError(
                f"Each {field_name} row must be an object "
                f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
            )
        _require_keys(row, {"chunk_id", "label"}, field_name, idx, strategy, row_idx)
        if row["label"] not in CHUNK_LABEL_TO_GAIN:
            raise ValueError(
                "chunk label must be one of "
                f"{sorted(CHUNK_LABEL_TO_GAIN)}"
                f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
            )


def _validate_chunk_ids_by_strategy(by_strategy: object, idx: int, field_name: str) -> None:
    for strategy, ids in _require_dict(by_strategy, field_name, idx).items():
        _validate_strategy_name(strategy, field_name, idx)
        if not isinstance(ids, list) or not all(isinstance(c, str) for c in ids):
            raise ValueError(
                f"Each {field_name} entry must be a list of chunk ids "
                f"(index {idx}, strategy {strategy})."
            )


def _validate_weak_labels_by_strategy(weak_by_strategy: object, idx: int) -> None:
    field_name = "weak_chunk_labels_by_strategy"
    for strategy, rows in _require_dict(weak_by_strategy, field_name, idx).items():
        _validate_strategy_name(strategy, field_name, idx)
        rows = _require_list(rows, f"Each {field_name} entry", idx, strategy=strategy)
        for row_idx, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(
                    "Each weak label row must be an object "
                    f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
                )
            _require_keys(
                row,
                {"chunk_id", "label", "confidence", "sources"},
                "weak label",
                idx,
                strategy,
                row_idx,
            )
            if row["label"] not in CHUNK_LABEL_TO_GAIN:
                raise ValueError(
                    f"Invalid weak label '{row['label']}' "
                    f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
                )
            if not isinstance(row["confidence"], (int, float)):
                raise ValueError(
                    "weak label confidence must be numeric "
                    f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
                )
            if not isinstance(row["sources"], list) or not all(
                isinstance(source, str) for source in row["sources"]
            ):
                raise ValueError(
                    "weak label sources must be a list[str] "
                    f"{_error_suffix(idx, strategy=strategy, row_idx=row_idx)}"
                )


def _validate_required_ground_truth_fields(item: dict, idx: int) -> None:
    required_keys = {"query", "lang", "relevant_docs"}
    missing = required_keys - set(item.keys())
    if missing:
        raise ValueError(f"Ground truth item at index {idx} missing keys: {sorted(missing)}")
    if not isinstance(item["relevant_docs"], list) or not item["relevant_docs"]:
        raise ValueError(
            f"Ground truth item at index {idx} must have a non-empty relevant_docs list."
        )
    for legacy_field in ("relevant_chunk_ids", "relevant_chunk_labels"):
        if legacy_field in item:
            raise ValueError(
                f"Legacy field '{legacy_field}' is not supported (index {idx}). "
                "Use strategy-specific fields instead."
            )


def _validate_relevant_chunk_labels_by_strategy_field(value: object, idx: int) -> None:
    labels_by_strategy = _require_dict(value, "relevant_chunk_labels_by_strategy", idx)
    for strategy, labels in labels_by_strategy.items():
        _validate_strategy_name(strategy, "relevant_chunk_labels_by_strategy", idx)
        _validate_chunk_labels(
            labels,
            idx,
            "relevant_chunk_labels_by_strategy",
            strategy=strategy,
        )


def _validate_relevant_chunk_ids_by_strategy_field(value: object, idx: int) -> None:
    _validate_chunk_ids_by_strategy(value, idx, "relevant_chunk_ids_by_strategy")


def _validate_weak_chunk_labels_by_strategy_field(value: object, idx: int) -> None:
    _validate_weak_labels_by_strategy(value, idx)


def _validate_weak_label_metadata_field(value: object, idx: int) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"weak_label_metadata must be an object (index {idx}).")


OPTIONAL_GROUND_TRUTH_FIELD_VALIDATORS: dict[str, Callable[[object, int], None]] = {
    "relevant_chunk_labels_by_strategy": _validate_relevant_chunk_labels_by_strategy_field,
    "relevant_chunk_ids_by_strategy": _validate_relevant_chunk_ids_by_strategy_field,
    "weak_chunk_labels_by_strategy": _validate_weak_chunk_labels_by_strategy_field,
    "weak_label_metadata": _validate_weak_label_metadata_field,
}


def _validate_optional_ground_truth_fields(item: dict, idx: int) -> None:
    for field_name, validator in OPTIONAL_GROUND_TRUTH_FIELD_VALIDATORS.items():
        if field_name in item:
            validator(item[field_name], idx)


def _validate_ground_truth_item(item: object, idx: int) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"Ground truth item at index {idx} must be an object.")
    _validate_required_ground_truth_fields(item, idx)
    _validate_optional_ground_truth_fields(item, idx)


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[dict]:
    """Load and validate benchmark ground truth queries."""
    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {path}")

    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("Ground truth must be a JSON array of query objects.")

    for idx, item in enumerate(data):
        _validate_ground_truth_item(item, idx)

    print(f"Loaded {len(data)} ground-truth queries from {path}")
    return data
