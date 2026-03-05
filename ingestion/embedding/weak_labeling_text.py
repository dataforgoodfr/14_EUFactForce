"""Text and scoring primitives for weak labeling."""

from __future__ import annotations

import re

from .weak_labeling_config import HIGH_THRESHOLD, PARTIAL_THRESHOLD


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def token_overlap(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = tokenize(text)
    if not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


def rank_to_score(rank: int | None, top_k: int) -> float:
    if rank is None or top_k <= 1:
        return 0.0
    bounded = min(max(rank, 1), top_k)
    return 1.0 - ((bounded - 1) / (top_k - 1))


def label_from_confidence(confidence: float) -> str:
    if confidence >= HIGH_THRESHOLD:
        return "high"
    if confidence >= PARTIAL_THRESHOLD:
        return "partial"
    return "irrelevant"
