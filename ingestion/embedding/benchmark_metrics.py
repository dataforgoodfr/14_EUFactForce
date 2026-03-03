"""Retrieval metric computation for embedding benchmark."""

from __future__ import annotations

import math

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .benchmark_config import CHUNK_K_VALUES, DOC_K_VALUES, POOL_TOP_K
from .benchmark_labels import normalize_chunk_labels


def _dcg(grades: list[float]) -> float:
    """Compute discounted cumulative gain."""
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def _rank_chunks_and_docs(scores: np.ndarray, chunks: list[dict]) -> tuple[list[dict], list[str], np.ndarray]:
    ranked_indices = np.argsort(scores)[::-1]
    ranked_chunks = [chunks[idx] for idx in ranked_indices]

    ranked_docs: list[str] = []
    seen_docs: set[str] = set()
    for chunk in ranked_chunks:
        doc_id = chunk["doc_id"]
        if doc_id not in seen_docs:
            ranked_docs.append(doc_id)
            seen_docs.add(doc_id)
    return ranked_chunks, ranked_docs, ranked_indices


def _doc_metrics_for_query(
    ranked_docs: list[str], relevant_docs: set[str], doc_k_values: list[int]
) -> tuple[dict[str, float], float]:
    per_k: dict[str, float] = {}
    for k in doc_k_values:
        top_k_docs = ranked_docs[:k]
        hits = len(set(top_k_docs) & relevant_docs)
        per_k[f"doc_level_precision@{k}"] = hits / min(k, len(relevant_docs))

    reciprocal_rank = 0.0
    for rank, doc_id in enumerate(ranked_docs, 1):
        if doc_id in relevant_docs:
            reciprocal_rank = 1.0 / rank
            break
    return per_k, reciprocal_rank


def _chunk_recall_and_hits_by_k(
    ranked_chunk_ids: list[str], relevant_chunk_ids: set[str], chunk_k_values: list[int]
) -> tuple[dict[str, float], dict[int, int]]:
    recalls_by_k: dict[str, float] = {}
    hits_by_k: dict[int, int] = {}
    for k in chunk_k_values:
        top_k_chunk_ids = ranked_chunk_ids[:k]
        hits = len(set(top_k_chunk_ids) & relevant_chunk_ids)
        recalls_by_k[f"chunk_level_recall@{k}"] = hits / len(relevant_chunk_ids)
        hits_by_k[k] = hits
    return recalls_by_k, hits_by_k


def _first_relevant_chunk_rank_and_rr(
    ranked_chunk_ids: list[str], relevant_chunk_ids: set[str]
) -> tuple[int, float]:
    for rank, chunk_id in enumerate(ranked_chunk_ids, 1):
        if chunk_id in relevant_chunk_ids:
            return rank, 1.0 / rank
    return -1, 0.0


def _ndcg_at_10(ranked_chunk_ids: list[str], graded_chunk_gains: dict[str, float]) -> float | None:
    if not graded_chunk_gains:
        return None
    observed_top10 = ranked_chunk_ids[:10]
    observed_grades = [graded_chunk_gains.get(chunk_id, 0.0) for chunk_id in observed_top10]
    ideal_grades = sorted(graded_chunk_gains.values(), reverse=True)[:10]
    ideal_dcg = _dcg(ideal_grades)
    return (_dcg(observed_grades) / ideal_dcg) if ideal_dcg > 0 else 0.0


def _chunk_metrics_for_query(
    ranked_chunks: list[dict],
    relevant_chunk_ids: set[str],
    graded_chunk_gains: dict[str, float],
    chunk_k_values: list[int],
) -> tuple[dict[str, float], float, float | None, int, dict[int, int]]:
    ranked_chunk_ids = [chunk["chunk_id"] for chunk in ranked_chunks]
    recalls_by_k, hits_by_k = _chunk_recall_and_hits_by_k(
        ranked_chunk_ids, relevant_chunk_ids, chunk_k_values
    )
    first_relevant_chunk_rank, chunk_rr = _first_relevant_chunk_rank_and_rr(
        ranked_chunk_ids, relevant_chunk_ids
    )
    ndcg_at_10 = _ndcg_at_10(ranked_chunk_ids, graded_chunk_gains)

    return recalls_by_k, chunk_rr, ndcg_at_10, first_relevant_chunk_rank, hits_by_k


def _label_source_mix(source: str) -> str:
    if source.startswith("manual_"):
        return "manual"
    if source.startswith("weak_"):
        return "weak"
    return "none"


def _initialize_metric_buckets(
    doc_k_values: list[int], chunk_k_values: list[int]
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    doc_metrics = {f"doc_level_precision@{k}": [] for k in doc_k_values}
    doc_metrics["doc_level_mrr"] = []

    chunk_metrics = {f"chunk_level_recall@{k}": [] for k in chunk_k_values}
    chunk_metrics["chunk_level_mrr"] = []
    chunk_metrics["chunk_level_ndcg@10"] = []
    return doc_metrics, chunk_metrics


def _append_doc_metrics(
    doc_metrics: dict[str, list[float]], doc_per_k: dict[str, float], doc_rr: float
) -> None:
    for key, value in doc_per_k.items():
        doc_metrics[key].append(value)
    doc_metrics["doc_level_mrr"].append(doc_rr)


def _append_chunk_metrics(
    chunk_metrics: dict[str, list[float]],
    recalls_by_k: dict[str, float],
    chunk_rr: float,
    ndcg_at_10: float | None,
) -> None:
    for key, value in recalls_by_k.items():
        chunk_metrics[key].append(value)
    chunk_metrics["chunk_level_mrr"].append(chunk_rr)
    if ndcg_at_10 is not None:
        chunk_metrics["chunk_level_ndcg@10"].append(ndcg_at_10)


def _first_relevant_doc_rank(ranked_docs: list[str], relevant_docs: set[str]) -> int:
    return next((rank for rank, doc_id in enumerate(ranked_docs, 1) if doc_id in relevant_docs), -1)


def _build_per_query_result(
    gt: dict,
    ranked_docs: list[str],
    ranked_chunks: list[dict],
    ranked_indices: np.ndarray,
    scores: np.ndarray,
    relevant_docs: set[str],
    relevant_chunk_ids: set[str],
    chunk_label_source: str,
    first_relevant_chunk_rank: int,
    relevant_hits_by_k: dict[int, int],
    chunk_k_values: list[int],
    pool_top_k: int,
) -> dict:
    return {
        "query": gt["query"],
        "lang": gt["lang"],
        "top_5_docs": ranked_docs[:5],
        "top_5_chunks": [
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "score": float(scores[ranked_indices[pos]]),
            }
            for pos, chunk in enumerate(ranked_chunks[:5])
        ],
        "top_pool_chunks": [
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in ranked_chunks[:pool_top_k]
        ],
        "relevant_docs": list(relevant_docs),
        "first_relevant_doc_rank": _first_relevant_doc_rank(ranked_docs, relevant_docs),
        "chunk_label_source": chunk_label_source,
        "chunk_label_source_mix": _label_source_mix(chunk_label_source),
        "relevant_chunks": sorted(relevant_chunk_ids),
        "first_relevant_chunk_rank": first_relevant_chunk_rank,
        "chunk_hits": (
            {f"@{k}": relevant_hits_by_k.get(k) for k in chunk_k_values} if relevant_chunk_ids else {}
        ),
    }


def _average_metric_buckets(
    doc_metrics: dict[str, list[float]], chunk_metrics: dict[str, list[float]]
) -> dict[str, float | None]:
    averaged: dict[str, float | None] = {}
    for key, values in doc_metrics.items():
        averaged[key] = float(np.mean(values)) if values else None
    for key, values in chunk_metrics.items():
        averaged[key] = float(np.mean(values)) if values else None
    return averaged


def compute_retrieval_metrics(
    query_embeddings: np.ndarray,
    chunk_embeddings: np.ndarray,
    chunks: list[dict],
    ground_truth: list[dict],
    chunking_strategy: str,
    doc_k_values: list[int] = DOC_K_VALUES,
    chunk_k_values: list[int] = CHUNK_K_VALUES,
    pool_top_k: int = POOL_TOP_K,
) -> dict:
    """
    Compute precision/recall/MRR metrics from chunk retrieval.

    Ranked chunks are collapsed to unique ranked docs for doc-level evaluation.
    """
    sim_matrix = cosine_similarity(query_embeddings, chunk_embeddings)
    doc_metrics, chunk_metrics = _initialize_metric_buckets(doc_k_values, chunk_k_values)
    per_query_results: list[dict] = []

    for query_idx, gt in enumerate(ground_truth):
        scores = sim_matrix[query_idx]
        ranked_chunks, ranked_docs, ranked_indices = _rank_chunks_and_docs(scores, chunks)
        relevant_docs = set(gt["relevant_docs"])

        doc_per_k, doc_rr = _doc_metrics_for_query(ranked_docs, relevant_docs, doc_k_values)
        _append_doc_metrics(doc_metrics, doc_per_k, doc_rr)

        relevant_chunk_ids, graded_chunk_gains, chunk_label_source = normalize_chunk_labels(
            gt, strategy=chunking_strategy
        )
        first_relevant_chunk_rank = -1
        relevant_hits_by_k: dict[int, int] = {}

        if relevant_chunk_ids:
            recalls_by_k, chunk_rr, ndcg_at_10, first_rank, hits_by_k = _chunk_metrics_for_query(
                ranked_chunks, relevant_chunk_ids, graded_chunk_gains, chunk_k_values
            )
            _append_chunk_metrics(chunk_metrics, recalls_by_k, chunk_rr, ndcg_at_10)

            first_relevant_chunk_rank = first_rank
            relevant_hits_by_k = hits_by_k

        per_query_results.append(
            _build_per_query_result(
                gt=gt,
                ranked_docs=ranked_docs,
                ranked_chunks=ranked_chunks,
                ranked_indices=ranked_indices,
                scores=scores,
                relevant_docs=relevant_docs,
                relevant_chunk_ids=relevant_chunk_ids,
                chunk_label_source=chunk_label_source,
                first_relevant_chunk_rank=first_relevant_chunk_rank,
                relevant_hits_by_k=relevant_hits_by_k,
                chunk_k_values=chunk_k_values,
                pool_top_k=pool_top_k,
            )
        )

    averaged = _average_metric_buckets(doc_metrics, chunk_metrics)
    return {"averaged": averaged, "per_query": per_query_results}
