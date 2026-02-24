from pathlib import Path

QUALITY_SCORES_CSV = Path("output/quality_scores.csv")
EXTRACTED_TEXT_DIR = Path("output/extracted_texts")
GROUND_TRUTH_JSON = Path("ground_truth/ground_truth.json")
GROUND_TRUTH_TEXT_DIR = Path("ground_truth/texts")

BASELINE_CSV = Path("output/fidelity_baseline_v1.csv")
BASELINE_DOC_TYPE_CSV = Path("output/fidelity_baseline_v1_by_doc_type.csv")
BASELINE_MD = Path("output/fidelity_baseline_v1_summary.md")
TAXONOMY_CSV = Path("output/fidelity_error_taxonomy.csv")
TAXONOMY_SUMMARY_CSV = Path("output/fidelity_error_taxonomy_summary.csv")
MATRIX_CSV = Path("output/fidelity_optimization_matrix.csv")
ROUTING_JSON = Path("output/parser_routing_by_doc_type.json")
LEADERBOARD_CSV = Path("output/fidelity_leaderboard.csv")
GATES_JSON = Path("output/fidelity_gates.json")

COMPOSITE_VERSION = "v1_0_35_25_25_15"  # Versioned fidelity weighting recipe for reproducible comparisons.
SENTENCE_MATCH_THRESHOLD = 0.80  # Minimum sentence similarity ratio to count as a match.
MIN_SENTENCE_LEN = 30
WINNER_MARGIN_THRESHOLD = 0.015  # Routing winner margin below this is flagged as low-confidence.
RECALL_FLOOR = 0.80  # Regression gate: minimum acceptable recall for candidate leaderboards.
GLOBAL_REGRESSION_MAX = 0.0  # Regression gate: candidate must not underperform baseline on average.
CRITICAL_ERROR_TYPES = ("missing_content", "order_violation")  # Taxonomy dimensions treated as highest impact.

# Taxonomy heuristics
AMBIGUOUS_MATCH_LOWER_BOUND = 0.70  # Near-match lower bound used to tag ambiguous hunks.
EARLY_MATCH_BREAK_THRESHOLD = 0.98  # Stop matching loop once a near-perfect match is found.
LENGTH_MISMATCH_RATIO = 0.50  # Skip candidate sentences with large relative length mismatch.
FRAGMENT_SHORT_LINE_MAX_WORDS = 3  # Short-line heuristic threshold for fragmentation counting.
FRAGMENT_SHORT_LINE_MAX_CHARS = 24  # Character-length companion threshold for short fragmented lines.
REPEATED_PARAGRAPH_MIN_CHARS = 50  # Ignore very short paragraphs when counting repeated content.

