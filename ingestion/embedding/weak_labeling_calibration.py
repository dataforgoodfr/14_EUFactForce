"""Calibration metrics for weak labels vs manual labels."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from .weak_labeling_config import GENERATOR_VERSION
from .weak_labeling_index import manual_positive_ids


def build_calibration_report(
    ground_truth: list[dict], strategies: tuple[str, ...]
) -> dict[str, object]:
    """Build macro precision/recall report for weak labels against manual labels."""
    report: dict[str, object] = {
        "generator_version": GENERATOR_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "strategies": {},
    }

    for strategy in strategies:
        precision_values: list[float] = []
        recall_values: list[float] = []
        evaluated = 0

        for row in ground_truth:
            manual = manual_positive_ids(row, strategy)
            weak_rows = (
                row.get("weak_chunk_labels_by_strategy", {}).get(strategy, [])
                if isinstance(row.get("weak_chunk_labels_by_strategy"), dict)
                else []
            )
            weak = {
                item["chunk_id"]
                for item in weak_rows
                if isinstance(item, dict) and item.get("label") in ("high", "partial")
            }
            if not manual:
                continue
            evaluated += 1
            if weak:
                precision_values.append(len(weak & manual) / len(weak))
            recall_values.append(len(weak & manual) / len(manual))

        report["strategies"][strategy] = {
            "evaluated_queries_with_manual_labels": evaluated,
            "macro_precision": round(float(np.mean(precision_values)), 4)
            if precision_values
            else None,
            "macro_recall": round(float(np.mean(recall_values)), 4) if recall_values else None,
        }

    return report
