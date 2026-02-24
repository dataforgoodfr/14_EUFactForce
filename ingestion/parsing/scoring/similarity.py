"""
Reference-text similarity scoring.

Compares extracted text against human-written ground truth texts
(from ground_truth/texts/) to measure parsing fidelity.

All metrics operate on body text only (references section stripped)
and use weighted scoring with a configurable threshold.
"""

from difflib import SequenceMatcher
from pathlib import Path

from .utils import (
    normalize_for_similarity,
    strip_references_section,
    split_sentences,
    best_match_ratio,
    LENGTH_MISMATCH_RATIO,
)

# Minimum match quality for a sentence to count as "recovered"
SENTENCE_MATCH_THRESHOLD = 0.80

# Minimum matched sentences required for order scoring to be meaningful
MIN_MATCHED_SENTENCES = 3

# Composite fidelity weights (sum = 1.0)
FIDELITY_WEIGHT_SIMILARITY = 0.35
FIDELITY_WEIGHT_RECALL = 0.25
FIDELITY_WEIGHT_PRECISION = 0.25
FIDELITY_WEIGHT_ORDER = 0.15


def _prepare_body(text: str) -> str:
    """Strip references and normalize for similarity comparison."""
    return normalize_for_similarity(strip_references_section(text))


def compute_text_similarity(extracted: str, reference: str) -> float:
    """
    Compute overall text similarity between extracted and reference texts
    using SequenceMatcher on normalized, body-only text (references stripped).

    Returns a ratio between 0.0 (completely different) and 1.0 (identical).
    """
    norm_ext = _prepare_body(extracted)
    norm_ref = _prepare_body(reference)
    return round(SequenceMatcher(None, norm_ref, norm_ext).ratio(), 4)


def compute_content_recall(
    extracted: str,
    reference: str,
    threshold: float = SENTENCE_MATCH_THRESHOLD,
) -> float:
    """
    Content recall: *weighted* fraction of reference body sentences recovered.

    Uses the actual best match ratio for each sentence.  A sentence matched
    at 0.85 contributes 0.85, not 1.0.  Sentences below *threshold* contribute 0.0.

    Returns a ratio between 0.0 and 1.0.
    """
    ref_sentences = split_sentences(_prepare_body(reference))
    if not ref_sentences:
        return 1.0

    ext_sentences = split_sentences(_prepare_body(extracted))
    if not ext_sentences:
        return 0.0

    ext_set = set(ext_sentences)
    total_score = sum(
        best
        for ref_s in ref_sentences
        if (best := best_match_ratio(ref_s, ext_sentences, ext_set)) >= threshold
    )
    return round(total_score / len(ref_sentences), 4)


def compute_content_precision(
    extracted: str,
    reference: str,
    threshold: float = SENTENCE_MATCH_THRESHOLD,
) -> float:
    """
    Content precision: *weighted* fraction of extraction body sentences
    that match the reference.

    Same weighted approach as recall.  References section stripped.

    Returns a ratio between 0.0 (all noise) and 1.0 (all valid content).
    """
    ext_sentences = split_sentences(_prepare_body(extracted))
    if not ext_sentences:
        return 0.0

    ref_sentences = split_sentences(_prepare_body(reference))
    if not ref_sentences:
        return 0.0

    ref_set = set(ref_sentences)
    total_score = sum(
        best
        for ext_s in ext_sentences
        if (best := best_match_ratio(ext_s, ref_sentences, ref_set)) >= threshold
    )
    return round(total_score / len(ext_sentences), 4)


def compute_order_score(
    extracted: str,
    reference: str,
    threshold: float = SENTENCE_MATCH_THRESHOLD,
) -> float | None:
    """
    Order preservation score with gap penalty.

    For each reference body sentence, records whether it was found in the
    extraction and at what position.  The score combines:
      - Concordant pair fraction (are found sentences in the right order?)
      - Coverage penalty (missing sentences count as order failures)

    Final score = concordant_fraction * coverage_fraction

    Returns a score between 0.0 and 1.0, or None if fewer than
    MIN_MATCHED_SENTENCES sentences matched.
    """
    ref_sentences = split_sentences(_prepare_body(reference))
    ext_sentences = split_sentences(_prepare_body(extracted))

    if len(ref_sentences) < MIN_MATCHED_SENTENCES or len(ext_sentences) < MIN_MATCHED_SENTENCES:
        return None

    ext_set = set(ext_sentences)
    matched_positions: list[tuple[int, int]] = []

    for ref_idx, ref_s in enumerate(ref_sentences):
        best_pos = -1
        best_ratio = 0.0

        if ref_s in ext_set:
            for ext_idx, ext_s in enumerate(ext_sentences):
                if ext_s == ref_s:
                    best_pos = ext_idx
                    best_ratio = 1.0
                    break
        else:
            for ext_idx, ext_s in enumerate(ext_sentences):
                if abs(len(ref_s) - len(ext_s)) > len(ref_s) * LENGTH_MISMATCH_RATIO:
                    continue
                ratio = SequenceMatcher(None, ref_s, ext_s).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pos = ext_idx

        if best_ratio >= threshold and best_pos >= 0:
            matched_positions.append((ref_idx, best_pos))

    if len(matched_positions) < MIN_MATCHED_SENTENCES:
        return None

    # Concordant pairs (correct relative order among matched sentences)
    concordant = 0
    total_pairs = 0
    for i in range(len(matched_positions)):
        for j in range(i + 1, len(matched_positions)):
            total_pairs += 1
            if matched_positions[i][1] < matched_positions[j][1]:
                concordant += 1

    concordant_frac = concordant / total_pairs if total_pairs > 0 else 0.0
    coverage = len(matched_positions) / len(ref_sentences)

    return round(concordant_frac * coverage, 4)


def score_reference_text(extracted_text: str, reference_path: Path) -> dict:
    """
    Compute all reference-text similarity metrics.

    Returns a dict with keys:
      text_similarity, content_recall, content_precision, order_score
    """
    reference_text = reference_path.read_text(encoding="utf-8")

    text_similarity = compute_text_similarity(extracted_text, reference_text)
    content_recall = compute_content_recall(extracted_text, reference_text)
    content_precision = compute_content_precision(extracted_text, reference_text)
    order_score = compute_order_score(extracted_text, reference_text)
    fidelity_composite = compute_fidelity_composite(
        text_similarity=text_similarity,
        content_recall=content_recall,
        content_precision=content_precision,
        order_score=order_score,
    )

    return {
        "fidelity_composite": fidelity_composite,
        "text_similarity": text_similarity,
        "content_recall": content_recall,
        "content_precision": content_precision,
        "order_score": order_score,
    }


def compute_fidelity_composite(
    text_similarity: float,
    content_recall: float,
    content_precision: float,
    order_score: float | None,
) -> float:
    """
    Weighted composite fidelity score in [0, 1].

    When order_score is None, use 0.0 for the weighted order term.
    """
    order = order_score if order_score is not None else 0.0
    score = (
        FIDELITY_WEIGHT_SIMILARITY * text_similarity
        + FIDELITY_WEIGHT_RECALL * content_recall
        + FIDELITY_WEIGHT_PRECISION * content_precision
        + FIDELITY_WEIGHT_ORDER * order
    )
    return round(score, 4)
