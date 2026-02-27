from __future__ import annotations

"""
Regression gates are a promotion-time safety check but not a scoring prerequisite.

Use this command when deciding whether to adopt a new candidate leaderboard
(e.g., before updating routing or promoting a new baseline). It compares
candidate vs baseline, prints PASS/FAIL in terminal, and writes a persistent
JSON report for artifact-driven workflows.
"""

import argparse
import json
from pathlib import Path

from fidelity.common import avg, load_quality_rows, to_float
from fidelity.constants import GLOBAL_REGRESSION_MAX, RECALL_FLOOR


def command_gates(args: argparse.Namespace) -> None:
    baseline_rows = load_quality_rows(Path(args.baseline))
    candidate_rows = load_quality_rows(Path(args.candidate))
    baseline_by_config = {r["parser_config"]: to_float(r.get("fidelity_composite_avg")) for r in baseline_rows}
    candidate_by_config = {r["parser_config"]: to_float(r.get("fidelity_composite_avg")) for r in candidate_rows}

    common_configs = sorted(set(baseline_by_config) & set(candidate_by_config))
    if not common_configs:
        raise ValueError("No overlapping parser_config values between baseline and candidate leaderboards.")

    deltas = []
    delta_rows: list[dict] = []
    for config in common_configs:
        b = baseline_by_config[config]
        c = candidate_by_config[config]
        if b is None or c is None:
            continue
        delta = c - b
        deltas.append(delta)
        delta_rows.append(
            {
                "parser_config": config,
                "baseline": round(b, 4),
                "candidate": round(c, 4),
                "delta": round(delta, 4),
            }
        )
        print(f"{config}: baseline={b:.4f} candidate={c:.4f} delta={delta:+.4f}")

    global_delta = avg(deltas) if deltas else None
    if global_delta is None:
        raise ValueError("Unable to compute global delta from provided files.")

    pass_global = global_delta >= GLOBAL_REGRESSION_MAX
    print(f"\nGlobal delta: {global_delta:+.4f}")
    print(f"Gate global_regression (>= {GLOBAL_REGRESSION_MAX:+.4f}): {'PASS' if pass_global else 'FAIL'}")

    # Optional recall floor check when candidate has recall column.
    recall_values = [
        to_float(r.get("content_recall_avg"))
        for r in candidate_rows
        if to_float(r.get("content_recall_avg")) is not None
    ]
    pass_recall = True
    min_recall = None
    if recall_values:
        min_recall = min(recall_values)
        pass_recall = min_recall >= RECALL_FLOOR
        print(f"Gate recall_floor (min >= {RECALL_FLOOR:.2f}): {'PASS' if pass_recall else 'FAIL'} (min={min_recall:.4f})")

    accepted = pass_global and pass_recall
    if accepted:
        print("\n[ACCEPT] Candidate passes regression gates.")
    else:
        print("\n[REJECT] Candidate fails regression gates.")

    report = {
        "baseline_path": str(args.baseline),
        "candidate_path": str(args.candidate),
        "thresholds": {
            "global_regression_max": GLOBAL_REGRESSION_MAX,
            "recall_floor": RECALL_FLOOR,
        },
        "global_delta": round(global_delta, 4),
        "global_regression_pass": pass_global,
        "min_recall": round(min_recall, 4) if min_recall is not None else None,
        "recall_floor_pass": pass_recall,
        "accepted": accepted,
        "config_deltas": delta_rows,
    }
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[OK] Gates report written to {output_path}")

