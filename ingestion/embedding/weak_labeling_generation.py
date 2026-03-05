"""Weak-label generation core flow."""

from __future__ import annotations

import random
from copy import deepcopy
from datetime import UTC, datetime

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .benchmark_embedding import embed_queries
from .weak_labeling_config import (
    DEFAULT_DENSE_TOP_K,
    DEFAULT_LEXICAL_TOP_K,
    DEFAULT_NEGATIVES,
    GENERATOR_VERSION,
    HIGH_THRESHOLD,
    PARTIAL_THRESHOLD,
    WEIGHT_ANCHOR_BONUS,
    WEIGHT_DENSE_SCORE,
    WEIGHT_LEXICAL_SCORE,
    WEIGHT_OVERLAP_SCORE,
)
from .weak_labeling_index import anchor_hits_for_query, build_strategy_index, load_key_passage_map
from .weak_labeling_text import label_from_confidence, rank_to_score, token_overlap, tokenize


def _dense_rank_for_relevant_docs(
    scores: np.ndarray, chunks: list[dict], relevant_docs: list[str], top_k_dense: int
) -> dict[str, int]:
    ranked_indices = np.argsort(scores)[::-1]
    rank = 0
    dense_rank: dict[str, int] = {}
    for idx in ranked_indices:
        chunk = chunks[idx]
        if chunk["doc_id"] not in relevant_docs:
            continue
        rank += 1
        dense_rank[chunk["chunk_id"]] = rank
        if rank >= top_k_dense:
            break
    return dense_rank


def _lexical_rank_for_relevant_docs(
    query_tokens: set[str], chunks: list[dict], relevant_docs: list[str], top_k_lexical: int
) -> tuple[dict[str, int], list[dict]]:
    lexical_pool = [chunk for chunk in chunks if chunk["doc_id"] in relevant_docs]
    lexical_sorted = sorted(
        lexical_pool,
        key=lambda chunk: token_overlap(query_tokens, chunk["text"]),
        reverse=True,
    )[:top_k_lexical]
    lexical_rank = {chunk["chunk_id"]: idx + 1 for idx, chunk in enumerate(lexical_sorted)}
    return lexical_rank, lexical_pool


def _sample_negatives(
    all_chunk_ids: list[str],
    chunk_by_id: dict[str, dict],
    candidate_ids: set[str],
    relevant_docs: list[str],
    negatives_per_query: int,
    rng: random.Random,
) -> set[str]:
    global_negatives = [
        cid
        for cid in all_chunk_ids
        if cid not in candidate_ids and chunk_by_id[cid]["doc_id"] not in relevant_docs
    ]
    rng.shuffle(global_negatives)
    return set(global_negatives[:negatives_per_query])


def _confidence_from_signals(
    dense_rank: dict[str, int],
    lexical_rank: dict[str, int],
    anchor_hits: set[str],
    chunk_id: str,
    query_tokens: set[str],
    chunk_text: str,
    top_k_dense: int,
    top_k_lexical: int,
) -> float:
    dense_score = rank_to_score(dense_rank.get(chunk_id), top_k_dense)
    lexical_score = rank_to_score(lexical_rank.get(chunk_id), top_k_lexical)
    overlap_score = token_overlap(query_tokens, chunk_text)
    anchor_bonus = 1.0 if chunk_id in anchor_hits else 0.0
    return (
        WEIGHT_DENSE_SCORE * dense_score
        + WEIGHT_LEXICAL_SCORE * lexical_score
        + WEIGHT_OVERLAP_SCORE * overlap_score
        + WEIGHT_ANCHOR_BONUS * anchor_bonus
    )


def _sources_for_chunk(
    chunk_id: str,
    dense_rank: dict[str, int],
    lexical_rank: dict[str, int],
    anchor_hits: set[str],
    sampled_negatives: set[str],
) -> list[str]:
    sources: list[str] = []
    if chunk_id in dense_rank:
        sources.append("dense")
    if chunk_id in lexical_rank:
        sources.append("lexical")
    if chunk_id in anchor_hits:
        sources.append("anchor_hit")
    if chunk_id in sampled_negatives:
        sources.append("negative_sample")
    return sources or ["fallback"]


def _build_weak_rows(
    final_ids: list[str],
    chunk_by_id: dict[str, dict],
    query_tokens: set[str],
    dense_rank: dict[str, int],
    lexical_rank: dict[str, int],
    anchor_hits: set[str],
    sampled_negatives: set[str],
    top_k_dense: int,
    top_k_lexical: int,
) -> list[dict]:
    weak_rows: list[dict] = []
    for chunk_id in final_ids:
        chunk_text = chunk_by_id[chunk_id]["text"]
        confidence = _confidence_from_signals(
            dense_rank,
            lexical_rank,
            anchor_hits,
            chunk_id,
            query_tokens,
            chunk_text,
            top_k_dense,
            top_k_lexical,
        )
        weak_rows.append(
            {
                "chunk_id": chunk_id,
                "label": label_from_confidence(confidence),
                "confidence": round(float(confidence), 4),
                "sources": _sources_for_chunk(
                    chunk_id, dense_rank, lexical_rank, anchor_hits, sampled_negatives
                ),
            }
        )
    weak_rows.sort(key=lambda row: row["confidence"], reverse=True)
    return weak_rows


def _apply_query_outputs(
    query_item: dict,
    strategy: str,
    weak_rows: list[dict],
    timestamp: str,
    model_name: str,
    top_k_dense: int,
    top_k_lexical: int,
    negatives_per_query: int,
    random_seed: int,
) -> None:
    query_item.setdefault("weak_chunk_labels_by_strategy", {})
    query_item["weak_chunk_labels_by_strategy"][strategy] = weak_rows

    query_item["weak_label_metadata"] = {
        "generator_version": GENERATOR_VERSION,
        "generated_at_utc": timestamp,
        "model_name": model_name,
        "thresholds": {"high": HIGH_THRESHOLD, "partial": PARTIAL_THRESHOLD},
        "top_k_dense": top_k_dense,
        "top_k_lexical": top_k_lexical,
        "negatives_per_query": negatives_per_query,
        "random_seed": random_seed,
    }


def _build_similarity_matrix(
    generated: list[dict], index: dict, use_dense: bool
) -> np.ndarray | None:
    if not use_dense:
        return None
    queries = [row["query"] for row in generated]
    query_embeddings = embed_queries(index["model"], queries, index["model_cfg"])
    return cosine_similarity(query_embeddings, index["chunk_embeddings"])


def _generate_query_weak_rows(
    query_item: dict,
    query_idx: int,
    chunks: list[dict],
    chunks_by_doc: dict[str, list[dict]],
    chunk_by_id: dict[str, dict],
    all_chunk_ids: list[str],
    key_passage_map: dict[str, str],
    sim_matrix: np.ndarray | None,
    top_k_dense: int,
    top_k_lexical: int,
    negatives_per_query: int,
    rng: random.Random,
) -> list[dict]:
    query = query_item["query"]
    relevant_docs = query_item.get("relevant_docs", [])
    if not isinstance(relevant_docs, list):
        relevant_docs = []
    query_tokens = tokenize(query)

    dense_rank: dict[str, int] = {}
    if sim_matrix is not None:
        dense_rank = _dense_rank_for_relevant_docs(
            sim_matrix[query_idx], chunks, relevant_docs, top_k_dense
        )

    lexical_rank, lexical_pool = _lexical_rank_for_relevant_docs(
        query_tokens, chunks, relevant_docs, top_k_lexical
    )
    anchor_hits = anchor_hits_for_query(relevant_docs, chunks_by_doc, key_passage_map)

    candidate_ids = set(dense_rank) | set(lexical_rank) | anchor_hits
    if not candidate_ids and lexical_pool:
        candidate_ids.add(lexical_pool[0]["chunk_id"])

    sampled_negatives = _sample_negatives(
        all_chunk_ids,
        chunk_by_id,
        candidate_ids,
        relevant_docs,
        negatives_per_query,
        rng,
    )
    final_ids = sorted(candidate_ids | sampled_negatives)
    return _build_weak_rows(
        final_ids,
        chunk_by_id,
        query_tokens,
        dense_rank,
        lexical_rank,
        anchor_hits,
        sampled_negatives,
        top_k_dense,
        top_k_lexical,
    )


def generate_weak_labels_data(
    ground_truth: list[dict],
    docs: dict[str, str],
    strategies: tuple[str, ...] = ("char", "paragraph"),
    model_name: str = "multilingual-e5-base",
    top_k_dense: int = DEFAULT_DENSE_TOP_K,
    top_k_lexical: int = DEFAULT_LEXICAL_TOP_K,
    negatives_per_query: int = DEFAULT_NEGATIVES,
    random_seed: int = 42,
    key_passages: dict[str, str] | None = None,
    use_dense: bool = True,
    generated_at_utc: str | None = None,
) -> list[dict]:
    """Generate weak labels for each query and chunking strategy."""
    key_passage_map = key_passages if key_passages is not None else load_key_passage_map()
    rng = random.Random(random_seed)
    generated = deepcopy(ground_truth)
    strategy_indexes = {
        strategy: build_strategy_index(
            docs, strategy=strategy, model_name=model_name, use_dense=use_dense
        )
        for strategy in strategies
    }
    timestamp = generated_at_utc or datetime.now(UTC).isoformat()

    for strategy in strategies:
        index = strategy_indexes[strategy]
        chunks = index["chunks"]
        chunks_by_doc = index["chunks_by_doc"]
        all_chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}

        sim_matrix = _build_similarity_matrix(generated, index, use_dense)

        for query_idx, query_item in enumerate(generated):
            weak_rows = _generate_query_weak_rows(
                query_item=query_item,
                query_idx=query_idx,
                chunks=chunks,
                chunks_by_doc=chunks_by_doc,
                chunk_by_id=chunk_by_id,
                all_chunk_ids=all_chunk_ids,
                key_passage_map=key_passage_map,
                sim_matrix=sim_matrix,
                top_k_dense=top_k_dense,
                top_k_lexical=top_k_lexical,
                negatives_per_query=negatives_per_query,
                rng=rng,
            )
            _apply_query_outputs(
                query_item,
                strategy,
                weak_rows,
                timestamp,
                model_name,
                top_k_dense,
                top_k_lexical,
                negatives_per_query,
                random_seed,
            )
    return generated
