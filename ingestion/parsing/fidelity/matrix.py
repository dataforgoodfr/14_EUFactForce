from __future__ import annotations

import argparse
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
    write_csv,
)


def command_matrix(args: argparse.Namespace) -> None:
    print(f"[INFO] Loading baseline rows from {args.baseline_csv}", flush=True)
    baseline_rows = load_quality_rows(Path(args.baseline_csv))
    print(f"[INFO] Loading taxonomy rows from {args.taxonomy_csv}", flush=True)
    taxonomy_rows = load_quality_rows(Path(args.taxonomy_csv))
    ensure_fidelity_composite(baseline_rows)
    fidelity_rows = [r for r in baseline_rows if to_float(r.get("fidelity_composite")) is not None]
    print(
        f"[INFO] Matrix input: {len(fidelity_rows)} fidelity rows, {len(taxonomy_rows)} taxonomy rows",
        flush=True,
    )

    taxonomy_by_key = {
        (r["filename"], r["parser_config"]): r
        for r in taxonomy_rows
    }

    matrix_rows: list[dict] = []
    for row in fidelity_rows:
        key = (row["filename"], row["parser_config"])
        tax = taxonomy_by_key.get(key)
        matrix_rows.append(
            {
                "filename": row["filename"],
                "doc_type": row.get("doc_type", ""),
                "parser_config": row["parser_config"],
                "parser_family": derive_parser_family(row["parser_config"]),
                "preprocess_profile": derive_preprocess_profile(row["parser_config"]),
                "postprocess_profile": derive_postprocess_profile(row["parser_config"]),
                "fidelity_composite": to_float(row.get("fidelity_composite")),
                "text_similarity": to_float(row.get("text_similarity")),
                "content_recall": to_float(row.get("content_recall")),
                "content_precision": to_float(row.get("content_precision")),
                "order_score": to_float(row.get("order_score")),
                "missing_content": int(tax["missing_content"]) if tax else None,
                "extra_content": int(tax["extra_content"]) if tax else None,
                "order_violation": int(tax["order_violation"]) if tax else None,
                "fragmentation_issue": int(tax["fragmentation_issue"]) if tax else None,
                "repeated_content": int(tax["repeated_content"]) if tax else None,
            }
        )

    write_csv(Path(args.output_csv), matrix_rows)

    grouped = group_rows(matrix_rows, ("parser_config", "preprocess_profile", "postprocess_profile"))
    ranked_rows = []
    for (parser_config, preprocess_profile, postprocess_profile), grp in grouped.items():
        fidelity = avg([r["fidelity_composite"] for r in grp])
        missing = avg([float(r["missing_content"]) for r in grp if r["missing_content"] is not None])
        extra = avg([float(r["extra_content"]) for r in grp if r["extra_content"] is not None])
        order_err = avg([float(r["order_violation"]) for r in grp if r["order_violation"] is not None])
        ranking_score = (fidelity or 0.0) - 0.005 * ((missing or 0.0) + (extra or 0.0) + (order_err or 0.0))
        ranked_rows.append(
            {
                "parser_config": parser_config,
                "preprocess_profile": preprocess_profile,
                "postprocess_profile": postprocess_profile,
                "num_documents": len(grp),
                "fidelity_composite_avg": round_opt(fidelity),
                "missing_content_avg": round_opt(missing, 2),
                "extra_content_avg": round_opt(extra, 2),
                "order_violation_avg": round_opt(order_err, 2),
                "ranking_score": round_opt(ranking_score),
            }
        )
    ranked_rows.sort(key=lambda r: r["ranking_score"] or 0.0, reverse=True)
    ranking_path = Path(args.output_csv).with_name("fidelity_optimization_matrix_ranked.csv")
    write_csv(ranking_path, ranked_rows)
    print(f"[OK] Optimization matrix written to {args.output_csv}")
    print(f"[OK] Ranked optimization matrix written to {ranking_path}")

