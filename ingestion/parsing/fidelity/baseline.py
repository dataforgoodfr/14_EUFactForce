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
from fidelity.constants import COMPOSITE_VERSION


def command_baseline(args: argparse.Namespace) -> None:
    print(f"[INFO] Loading quality scores from {args.quality_csv}", flush=True)
    rows = load_quality_rows(Path(args.quality_csv))
    ensure_fidelity_composite(rows)
    fidelity_rows = [r for r in rows if to_float(r.get("fidelity_composite")) is not None]
    print(f"[INFO] Rows with fidelity metrics: {len(fidelity_rows)}", flush=True)

    grouped = group_rows(fidelity_rows, ("parser_config",))
    baseline_rows = []
    for (parser_config,), grp in grouped.items():
        baseline_rows.append(
            {
                "parser_config": parser_config,
                "parser_family": derive_parser_family(parser_config),
                "preprocess_profile": derive_preprocess_profile(parser_config),
                "postprocess_profile": derive_postprocess_profile(parser_config),
                "num_documents": len(grp),
                "composite_version": COMPOSITE_VERSION,
                "fidelity_composite_avg": round_opt(avg([to_float(r.get("fidelity_composite")) for r in grp])),
                "text_similarity_avg": round_opt(avg([to_float(r.get("text_similarity")) for r in grp])),
                "content_recall_avg": round_opt(avg([to_float(r.get("content_recall")) for r in grp])),
                "content_precision_avg": round_opt(avg([to_float(r.get("content_precision")) for r in grp])),
                "order_score_avg": round_opt(avg([to_float(r.get("order_score")) for r in grp])),
            }
        )

    baseline_rows.sort(key=lambda r: r["fidelity_composite_avg"] or 0.0, reverse=True)
    write_csv(Path(args.output_csv), baseline_rows)

    by_doc_type = group_rows(fidelity_rows, ("doc_type", "parser_config"))
    by_doc_type_rows = []
    for (doc_type, parser_config), grp in by_doc_type.items():
        by_doc_type_rows.append(
            {
                "doc_type": doc_type,
                "parser_config": parser_config,
                "parser_family": derive_parser_family(parser_config),
                "preprocess_profile": derive_preprocess_profile(parser_config),
                "postprocess_profile": derive_postprocess_profile(parser_config),
                "num_documents": len(grp),
                "composite_version": COMPOSITE_VERSION,
                "fidelity_composite_avg": round_opt(avg([to_float(r.get("fidelity_composite")) for r in grp])),
                "text_similarity_avg": round_opt(avg([to_float(r.get("text_similarity")) for r in grp])),
                "content_recall_avg": round_opt(avg([to_float(r.get("content_recall")) for r in grp])),
                "content_precision_avg": round_opt(avg([to_float(r.get("content_precision")) for r in grp])),
                "order_score_avg": round_opt(avg([to_float(r.get("order_score")) for r in grp])),
            }
        )
    by_doc_type_rows.sort(
        key=lambda r: (r["doc_type"], -(r["fidelity_composite_avg"] or 0.0))
    )
    write_csv(Path(args.output_doc_type_csv), by_doc_type_rows)
    write_baseline_markdown(Path(args.output_md), baseline_rows, by_doc_type_rows)
    print(f"[OK] Baseline leaderboard written to {args.output_csv}")
    print(f"[OK] Doc-type leaderboard written to {args.output_doc_type_csv}")
    print(f"[OK] Baseline summary written to {args.output_md}")


def write_baseline_markdown(path: Path, global_rows: list[dict], by_doc_type_rows: list[dict]) -> None:
    lines = [
        "# Fidelity Baseline v1",
        "",
        f"- Composite version: `{COMPOSITE_VERSION}`",
        f"- Configs ranked: `{len(global_rows)}`",
        "",
        "## Global Ranking",
        "",
        "| Rank | Parser Config | Composite | Similarity | Recall | Precision | Order |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in enumerate(global_rows, start=1):
        lines.append(
            f"| {idx} | `{row['parser_config']}` | {row['fidelity_composite_avg']:.4f} | "
            f"{row['text_similarity_avg']:.4f} | {row['content_recall_avg']:.4f} | "
            f"{row['content_precision_avg']:.4f} | {row['order_score_avg'] if row['order_score_avg'] is not None else 'n/a'} |"
        )

    lines.extend(["", "## Best By Doc Type", ""])
    current = None
    for row in by_doc_type_rows:
        if row["doc_type"] != current:
            current = row["doc_type"]
            lines.append(f"### `{current}`")
        lines.append(
            f"- `{row['parser_config']}`: composite={row['fidelity_composite_avg']:.4f}, "
            f"similarity={row['text_similarity_avg']:.4f}, recall={row['content_recall_avg']:.4f}, "
            f"precision={row['content_precision_avg']:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

