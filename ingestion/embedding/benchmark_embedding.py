"""Embedding model load/encode helpers."""

from __future__ import annotations

import numpy as np


def load_model(model_config: dict):
    """Load an embedding model via sentence-transformers."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_config["model_id"])


def _prefix_texts(texts: list[str], prefix: str) -> list[str]:
    return [f"{prefix}{text}" for text in texts]


def embed_texts(model, texts: list[str], model_config: dict) -> np.ndarray:
    """Embed a list of passage texts."""
    prefixed = _prefix_texts(texts, model_config.get("passage_prefix", ""))
    return model.encode(prefixed, show_progress_bar=False, normalize_embeddings=True)


def embed_queries(model, queries: list[str], model_config: dict) -> np.ndarray:
    """Embed a list of query texts."""
    prefixed = _prefix_texts(queries, model_config.get("query_prefix", ""))
    return model.encode(prefixed, show_progress_bar=False, normalize_embeddings=True)
