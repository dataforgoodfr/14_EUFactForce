"""Benchmark reporting and output serialization helpers."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .benchmark_config import (
    OUTPUT_DIR,
    POOL_RANDOM_NEGATIVES,
    POOL_RANDOM_SEED,
    POOL_TOP_K,
)


def _collect_top_pool_chunk_ids(
    all_results: list[dict], query_index: int, top_k_per_model: int
) -> set[str]:
    """Collect pooled chunk ids from each model for one query index."""
    pooled_chunk_ids: set[str] = set()
    for result in all_results:
        model_row = result["per_query_results"][query_index]
        top_pool = model_row.get("top_pool_chunks", [])[:top_k_per_model]
        pooled_chunk_ids.update(chunk["chunk_id"] for chunk in top_pool)
    return pooled_chunk_ids


def _sample_contrast_chunk_ids(
    pooled_chunk_ids: set[str],
    all_chunk_ids: list[str],
    rng: np.random.Generator,
    random_contrast_samples: int,
) -> set[str]:
    """Sample chunk ids not already in the pooled set."""
    if random_contrast_samples <= 0:
        return set()
    available_contrast = [chunk_id for chunk_id in all_chunk_ids if chunk_id not in pooled_chunk_ids]
    if not available_contrast:
        return set()
    sample_size = min(random_contrast_samples, len(available_contrast))
    sampled = rng.choice(available_contrast, size=sample_size, replace=False)
    return {str(item) for item in sampled.tolist()}


def _build_candidates_from_ids(pooled_chunk_ids: set[str], chunk_lookup: dict[str, dict]) -> list[dict]:
    """Build candidate payload rows for pooled chunk ids."""
    candidates: list[dict] = []
    for chunk_id in sorted(pooled_chunk_ids):
        chunk = chunk_lookup.get(chunk_id)
        if not chunk:
            continue
        candidates.append(
            {
                "chunk_id": chunk_id,
                "doc_id": chunk["doc_id"],
                "chunk_index": int(chunk["chunk_index"]),
                "text_preview": chunk["text"][:280],
                "label": "unjudged",
            }
        )
    return candidates


def _build_query_pool_row(query_row: dict, candidates: list[dict]) -> dict:
    """Build one query-level judging pool row."""
    return {
        "query": query_row["query"],
        "lang": query_row["lang"],
        "relevant_docs": query_row["relevant_docs"],
        "candidates": candidates,
    }


def build_judging_pool(
    all_results: list[dict],
    chunk_lookup: dict[str, dict],
    top_k_per_model: int = POOL_TOP_K,
    random_contrast_samples: int = POOL_RANDOM_NEGATIVES,
) -> list[dict]:
    """Build pooled judging candidates from model top-k chunks per query."""
    if not all_results:
        return []

    rng = np.random.default_rng(POOL_RANDOM_SEED)
    query_count = len(all_results[0]["per_query_results"])
    all_chunk_ids = list(chunk_lookup.keys())
    pooled: list[dict] = []

    for query_index in range(query_count):
        query_row = all_results[0]["per_query_results"][query_index]
        pooled_chunk_ids = _collect_top_pool_chunk_ids(all_results, query_index, top_k_per_model)
        pooled_chunk_ids.update(
            _sample_contrast_chunk_ids(
                pooled_chunk_ids=pooled_chunk_ids,
                all_chunk_ids=all_chunk_ids,
                rng=rng,
                random_contrast_samples=random_contrast_samples,
            )
        )
        candidates = _build_candidates_from_ids(pooled_chunk_ids, chunk_lookup)
        pooled.append(_build_query_pool_row(query_row, candidates))
    return pooled


def print_comparison_table(all_results: list[dict]) -> None:
    """Print a comparison table of all models."""
    print(f"\n{'=' * 80}")
    print("COMPARISON TABLE")
    print(f"{'=' * 80}")

    header = (
        f"{'Model':<25} {'Dim':>5} {'DocP@3':>8} {'DocP@5':>8} "
        f"{'DocMRR':>8} {'ChkR@5':>8} {'ChkMRR':>8} {'Speed':>10} {'Load':>7}"
    )
    print(header)
    print("-" * len(header))

    for row in all_results:
        chunk_r5 = row.get("chunk_level_recall@5")
        chunk_mrr = row.get("chunk_level_mrr")
        chunk_r5_str = f"{chunk_r5:>8.3f}" if chunk_r5 is not None else f"{'n/a':>8}"
        chunk_mrr_str = f"{chunk_mrr:>8.3f}" if chunk_mrr is not None else f"{'n/a':>8}"
        print(
            f"{row['model_name']:<25} "
            f"{row['embedding_dim']:>5} "
            f"{row['doc_level_precision@3']:>8.3f} "
            f"{row['doc_level_precision@5']:>8.3f} "
            f"{row['doc_level_mrr']:>8.3f} "
            f"{chunk_r5_str} "
            f"{chunk_mrr_str} "
            f"{row['chunks_per_second']:>7.1f}c/s "
            f"{row['load_time_s']:>5.1f}s"
        )

    print("\n  Cross-language breakdown:")
    for row in all_results:
        en_doc_ranks = [
            item["first_relevant_doc_rank"]
            for item in row["per_query_results"]
            if item["lang"] == "en" and item["first_relevant_doc_rank"] > 0
        ]
        fr_doc_ranks = [
            item["first_relevant_doc_rank"]
            for item in row["per_query_results"]
            if item["lang"] == "fr" and item["first_relevant_doc_rank"] > 0
        ]
        en_doc = float(np.mean(en_doc_ranks)) if en_doc_ranks else float("nan")
        fr_doc = float(np.mean(fr_doc_ranks)) if fr_doc_ranks else float("nan")

        en_chunk_ranks = [
            item["first_relevant_chunk_rank"]
            for item in row["per_query_results"]
            if item["lang"] == "en" and item["first_relevant_chunk_rank"] > 0
        ]
        fr_chunk_ranks = [
            item["first_relevant_chunk_rank"]
            for item in row["per_query_results"]
            if item["lang"] == "fr" and item["first_relevant_chunk_rank"] > 0
        ]
        en_chunk = float(np.mean(en_chunk_ranks)) if en_chunk_ranks else float("nan")
        fr_chunk = float(np.mean(fr_chunk_ranks)) if fr_chunk_ranks else float("nan")
        chunk_note = (
            f" | chunk first hit rank EN/FR: {en_chunk:.1f}/{fr_chunk:.1f}"
            if en_chunk_ranks or fr_chunk_ranks
            else ""
        )
        print(
            f"    {row['model_name']:<25} doc first hit rank EN/FR: {en_doc:.1f}/{fr_doc:.1f}"
            f"{chunk_note}"
        )


def save_results(
    all_results: list[dict], chunk_lookup: dict[str, dict], strategy: str, multi_run: bool
) -> None:
    """Persist benchmark outputs, adding strategy suffix in multi-run mode."""
    suffix = f"_{strategy}" if multi_run else ""
    output_path = OUTPUT_DIR / f"embedding_benchmark_results{suffix}.json"

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(list(all_results), handle, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_path}")

    summary_rows = [{k: v for k, v in row.items() if k != "per_query_results"} for row in all_results]
    df = pd.DataFrame(summary_rows)
    csv_path = OUTPUT_DIR / f"embedding_benchmark_summary{suffix}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Summary CSV saved to: {csv_path}")

    pool = build_judging_pool(all_results, chunk_lookup)
    pool_path = OUTPUT_DIR / f"chunk_judging_pool{suffix}.json"
    with open(pool_path, "w", encoding="utf-8") as handle:
        json.dump(pool, handle, indent=2, ensure_ascii=False)
    print(f"Judging pool saved to: {pool_path}")
