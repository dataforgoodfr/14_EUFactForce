"""Chunk-label normalization helpers for benchmark scoring."""

from __future__ import annotations

from .benchmark_config import CHUNK_LABEL_TO_GAIN


def _manual_chunk_ids_for_strategy(gt_item: dict, strategy: str) -> list[str]:
    """Return manual strategy-specific chunk ids for a strategy."""
    by_strategy = gt_item.get("relevant_chunk_ids_by_strategy")
    if isinstance(by_strategy, dict):
        strategy_ids = by_strategy.get(strategy, [])
        if isinstance(strategy_ids, list):
            return [chunk_id for chunk_id in strategy_ids if isinstance(chunk_id, str)]
    return []


def _manual_chunk_labels_for_strategy(gt_item: dict, strategy: str) -> list[dict]:
    """Return manual strategy-specific graded labels for a strategy."""
    by_strategy = gt_item.get("relevant_chunk_labels_by_strategy")
    if isinstance(by_strategy, dict):
        strategy_labels = by_strategy.get(strategy, [])
        if isinstance(strategy_labels, list):
            return [row for row in strategy_labels if isinstance(row, dict)]
    return []


def normalize_chunk_labels(
    gt_item: dict, strategy: str
) -> tuple[set[str], dict[str, float], str]:
    """
    Return (binary_relevant_chunk_ids, graded_gain_by_chunk_id, source_kind).

    source_kind:
      - "none": no chunk labels on this query
      - "manual_binary": only manual binary labels
      - "manual_graded": manual graded labels
    """
    manual_binary = set(_manual_chunk_ids_for_strategy(gt_item, strategy))
    manual_rows = _manual_chunk_labels_for_strategy(gt_item, strategy)
    manual_graded: dict[str, float] = {}

    for row in manual_rows:
        chunk_id = row["chunk_id"]
        gain = CHUNK_LABEL_TO_GAIN[row["label"]]
        manual_graded[chunk_id] = gain
        if gain > 0:
            manual_binary.add(chunk_id)

    if manual_graded:
        return manual_binary, manual_graded, "manual_graded"
    if manual_binary:
        return manual_binary, {}, "manual_binary"
    return set(), {}, "none"
