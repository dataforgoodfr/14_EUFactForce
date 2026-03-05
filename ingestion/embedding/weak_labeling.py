"""Thin compatibility module for weak-labeling APIs."""

from __future__ import annotations

from ingestion.embedding.weak_labeling_calibration import build_calibration_report
from ingestion.embedding.weak_labeling_config import (
    DEFAULT_DENSE_TOP_K,
    DEFAULT_LEXICAL_TOP_K,
    DEFAULT_NEGATIVES,
    GENERATOR_VERSION,
    HIGH_THRESHOLD,
    PARTIAL_THRESHOLD,
)
from ingestion.embedding.weak_labeling_generation import generate_weak_labels_data
from ingestion.embedding.weak_labeling_io import run_weak_label_generation

__all__ = [
    "GENERATOR_VERSION",
    "HIGH_THRESHOLD",
    "PARTIAL_THRESHOLD",
    "DEFAULT_DENSE_TOP_K",
    "DEFAULT_LEXICAL_TOP_K",
    "DEFAULT_NEGATIVES",
    "generate_weak_labels_data",
    "build_calibration_report",
    "run_weak_label_generation",
]
