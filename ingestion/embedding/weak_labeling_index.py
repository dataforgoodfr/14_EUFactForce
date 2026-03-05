"""Indexing helpers for weak-label generation."""

from __future__ import annotations

import json
from pathlib import Path

from .benchmark_chunking import build_chunks
from .benchmark_config import CANDIDATE_MODELS, CHUNK_LABEL_TO_GAIN
from .benchmark_embedding import embed_texts, load_model
from .weak_labeling_text import normalize_text, token_overlap, tokenize

POSITIVE_CHUNK_LABELS = {label for label, gain in CHUNK_LABEL_TO_GAIN.items() if gain > 0}


def load_key_passage_map() -> dict[str, str]:
    """Load document-level key passages from parsing ground truth."""
    gt_path = (
        Path(__file__).parent.parent / "parsing" / "ground_truth" / "ground_truth.json"
    )
    if not gt_path.exists():
        return {}

    data = json.loads(gt_path.read_text(encoding="utf-8"))
    docs = data.get("documents", {})
    out: dict[str, str] = {}
    for pdf_name, row in docs.items():
        key_passage = (row or {}).get("key_passage")
        if not isinstance(key_passage, str) or not key_passage.strip():
            continue
        out[pdf_name.replace(".pdf", "")] = key_passage.strip()
    return out


def manual_positive_ids(query_item: dict, strategy: str) -> set[str]:
    """Return manual positive (relevant) ids for one query and strategy."""
    positives: set[str] = set()

    labels_by_strategy = query_item.get("relevant_chunk_labels_by_strategy", {})
    if isinstance(labels_by_strategy, dict):
        strategy_labels = labels_by_strategy.get(strategy, [])
        if isinstance(strategy_labels, list):
            for row in strategy_labels:
                if (
                    isinstance(row, dict)
                    and isinstance(row.get("chunk_id"), str)
                    and row.get("label") in POSITIVE_CHUNK_LABELS
                ):
                    positives.add(row["chunk_id"])

    ids_by_strategy = query_item.get("relevant_chunk_ids_by_strategy", {})
    if isinstance(ids_by_strategy, dict):
        strategy_ids = ids_by_strategy.get(strategy, [])
        if isinstance(strategy_ids, list):
            positives.update({cid for cid in strategy_ids if isinstance(cid, str)})
    return positives


def build_strategy_index(
    docs: dict[str, str], strategy: str, model_name: str, use_dense: bool
) -> dict[str, object]:
    """Build chunk index + optional dense embeddings for one strategy."""
    chunks = build_chunks(docs, strategy=strategy)
    model_cfg = CANDIDATE_MODELS[model_name] if use_dense else None
    model = load_model(model_cfg) if use_dense else None
    chunk_embeddings = None
    if use_dense:
        chunk_texts = [chunk["text"] for chunk in chunks]
        chunk_embeddings = embed_texts(model, chunk_texts, model_cfg)

    chunks_by_doc: dict[str, list[dict]] = {}
    for chunk in chunks:
        chunks_by_doc.setdefault(chunk["doc_id"], []).append(chunk)

    return {
        "strategy": strategy,
        "model_cfg": model_cfg,
        "model": model,
        "chunks": chunks,
        "chunk_embeddings": chunk_embeddings,
        "chunks_by_doc": chunks_by_doc,
    }


def anchor_hits_for_query(
    relevant_docs: list[str],
    chunks_by_doc: dict[str, list[dict]],
    key_passages: dict[str, str],
) -> set[str]:
    """Return chunk ids aligned with key passages for relevant docs."""
    hits: set[str] = set()
    for doc_id in relevant_docs:
        key_passage = key_passages.get(doc_id)
        if not key_passage:
            continue
        normalized_key = normalize_text(key_passage)
        key_tokens = tokenize(key_passage)

        best_chunk_id: str | None = None
        best_overlap = 0.0
        for chunk in chunks_by_doc.get(doc_id, []):
            chunk_text = chunk["text"]
            if normalized_key and normalized_key in normalize_text(chunk_text):
                hits.add(chunk["chunk_id"])
                continue
            overlap = token_overlap(key_tokens, chunk_text)
            if overlap > best_overlap:
                best_overlap = overlap
                best_chunk_id = chunk["chunk_id"]

        if best_chunk_id and best_overlap >= 0.45:
            hits.add(best_chunk_id)
    return hits
