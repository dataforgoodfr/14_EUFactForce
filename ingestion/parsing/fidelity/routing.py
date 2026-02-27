from __future__ import annotations

import argparse
import json
from pathlib import Path

from fidelity.common import (
    avg,
    derive_parser_family,
    derive_postprocess_profile,
    derive_preprocess_profile,
    ensure_fidelity_composite,
    group_rows,
    load_quality_rows,
    round_opt,
    to_float,
)
from fidelity.constants import COMPOSITE_VERSION, WINNER_MARGIN_THRESHOLD


def command_routing(args: argparse.Namespace) -> None:
    print(f"[INFO] Loading quality rows from {args.quality_csv}", flush=True)
    rows = load_quality_rows(Path(args.quality_csv))
    ensure_fidelity_composite(rows)
    fidelity_rows = [r for r in rows if to_float(r.get("fidelity_composite")) is not None]
    print(f"[INFO] Routing rows with fidelity metrics: {len(fidelity_rows)}", flush=True)
    grouped = group_rows(fidelity_rows, ("doc_type", "parser_config"))

    by_doc_type: dict[str, list[dict]] = {}
    for (doc_type, parser_config), grp in grouped.items():
        by_doc_type.setdefault(doc_type, []).append(
            {
                "parser_config": parser_config,
                "parser_family": derive_parser_family(parser_config),
                "preprocess_profile": derive_preprocess_profile(parser_config),
                "postprocess_profile": derive_postprocess_profile(parser_config),
                "num_documents": len(grp),
                "fidelity_composite_avg": round_opt(avg([to_float(r.get("fidelity_composite")) for r in grp])),
                "content_recall_avg": round_opt(avg([to_float(r.get("content_recall")) for r in grp])),
            }
        )

    routing = {
        "composite_version": COMPOSITE_VERSION,
        "winner_margin_threshold": WINNER_MARGIN_THRESHOLD,
        "doc_type_routing": {},
    }

    for doc_type, candidates in by_doc_type.items():
        candidates.sort(key=lambda r: r["fidelity_composite_avg"] or 0.0, reverse=True)
        best = candidates[0]
        fallback = candidates[1] if len(candidates) > 1 else None
        margin = (
            (best["fidelity_composite_avg"] or 0.0) - (fallback["fidelity_composite_avg"] or 0.0)
            if fallback else None
        )
        low_confidence = margin is not None and margin < WINNER_MARGIN_THRESHOLD
        routing["doc_type_routing"][doc_type] = {
            "recommended": best,
            "fallback": fallback,
            "winner_margin": round_opt(margin),
            "low_confidence": low_confidence,
        }

    Path(args.output_json).write_text(json.dumps(routing, indent=2), encoding="utf-8")
    print(f"[OK] Routing recommendations written to {args.output_json}")

