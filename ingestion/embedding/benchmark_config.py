"""Shared configuration/constants for embedding benchmark."""

from __future__ import annotations

import os
from pathlib import Path

EXTRACTED_TEXTS_DIR = Path(__file__).parent.parent / "parsing" / "output" / "extracted_texts"
OUTPUT_DIR = Path(__file__).parent / "output"
GROUND_TRUTH_PATH = Path(__file__).parent / "data" / "ground_truth.json"

CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200
CHUNKING_STRATEGY = os.getenv("EMBEDDING_CHUNKING_STRATEGY", "paragraph")
VALID_CHUNKING_STRATEGIES = {"char", "paragraph"}

DOC_K_VALUES = [3, 5, 10]
CHUNK_K_VALUES = [1, 3, 5, 10]
POOL_TOP_K = 10
POOL_RANDOM_NEGATIVES = 2
POOL_RANDOM_SEED = 42
CHUNK_LABEL_TO_GAIN = {"high": 2.0, "partial": 1.0, "irrelevant": 0.0}

CANDIDATE_MODELS = {
    "multilingual-e5-base": {
        "model_id": "intfloat/multilingual-e5-base",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
}
