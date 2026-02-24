"""
Ground-truth-driven fidelity optimization toolkit.

This module provides reusable CLI commands for:
  - baseline leaderboard generation
  - deterministic error taxonomy extraction
  - parser/preprocess optimization matrix ranking
  - doc-type routing recommendations
  - regression acceptance gates
"""

from __future__ import annotations

import argparse

from fidelity.baseline import command_baseline
from fidelity.constants import (
    BASELINE_CSV,
    BASELINE_DOC_TYPE_CSV,
    BASELINE_MD,
    EXTRACTED_TEXT_DIR,
    GATES_JSON,
    GROUND_TRUTH_JSON,
    GROUND_TRUTH_TEXT_DIR,
    LEADERBOARD_CSV,
    MATRIX_CSV,
    QUALITY_SCORES_CSV,
    ROUTING_JSON,
    TAXONOMY_CSV,
    TAXONOMY_SUMMARY_CSV,
)
from fidelity.gates import command_gates
from fidelity.matrix import command_matrix
from fidelity.routing import command_routing
from fidelity.taxonomy import command_taxonomy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fidelity optimization toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_baseline = sub.add_parser("baseline", help="Generate baseline leaderboard artifacts")
    p_baseline.set_defaults(
        func=command_baseline,
        quality_csv=str(QUALITY_SCORES_CSV),
        output_csv=str(BASELINE_CSV),
        output_doc_type_csv=str(BASELINE_DOC_TYPE_CSV),
        output_md=str(BASELINE_MD),
    )

    p_tax = sub.add_parser("taxonomy", help="Generate deterministic fidelity error taxonomy")
    p_tax.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N processed (doc,config) pairs.",
    )
    p_tax.set_defaults(
        func=command_taxonomy,
        ground_truth_json=str(GROUND_TRUTH_JSON),
        ground_truth_text_dir=str(GROUND_TRUTH_TEXT_DIR),
        extracted_text_dir=str(EXTRACTED_TEXT_DIR),
        output_csv=str(TAXONOMY_CSV),
        output_summary_csv=str(TAXONOMY_SUMMARY_CSV),
    )

    p_matrix = sub.add_parser("matrix", help="Build optimization matrix and ranking")
    p_matrix.set_defaults(
        func=command_matrix,
        baseline_csv=str(QUALITY_SCORES_CSV),
        taxonomy_csv=str(TAXONOMY_CSV),
        output_csv=str(MATRIX_CSV),
    )

    p_routing = sub.add_parser("routing", help="Create doc-type parser routing recommendations")
    p_routing.set_defaults(
        func=command_routing,
        quality_csv=str(QUALITY_SCORES_CSV),
        output_json=str(ROUTING_JSON),
    )

    p_gates = sub.add_parser("gates", help="Evaluate regression gates")
    p_gates.set_defaults(
        func=command_gates,
        baseline=str(BASELINE_CSV),
        candidate=str(LEADERBOARD_CSV),
        output_json=str(GATES_JSON),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
