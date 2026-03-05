"""I/O orchestration for weak-label generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .benchmark_config import OUTPUT_DIR
from .benchmark_data import load_documents, load_ground_truth
from .weak_labeling_calibration import build_calibration_report
from .weak_labeling_generation import generate_weak_labels_data


def run_weak_label_generation(
    input_path: Path,
    output_path: Path,
    strategy_mode: Literal["char", "paragraph"] = "paragraph",
) -> tuple[Path, Path]:
    """Generate weak labels, write updated ground truth and calibration report."""
    ground_truth = load_ground_truth(path=input_path)
    docs = load_documents()

    strategies = (strategy_mode,)
    generated = generate_weak_labels_data(
        ground_truth=ground_truth,
        docs=docs,
        strategies=strategies,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(generated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    calibration = build_calibration_report(generated, strategies=strategies)
    calibration_path = OUTPUT_DIR / f"weak_label_calibration_report_{strategy_mode}.json"
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(
        json.dumps(calibration, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Weak-labeled ground truth saved to: {output_path}")
    print(f"Weak-label calibration report saved to: {calibration_path}")
    return output_path, calibration_path
