"""Orchestration/CLI for embedding benchmark."""

from __future__ import annotations

import argparse

from ingestion.timing import timed_call

from .benchmark_chunking import build_chunk_lookup, build_chunks
from .benchmark_config import CANDIDATE_MODELS, CHUNKING_STRATEGY, OUTPUT_DIR
from .benchmark_data import load_documents, load_ground_truth
from .benchmark_embedding import embed_queries, embed_texts, load_model
from .benchmark_metrics import compute_retrieval_metrics
from .benchmark_output import print_comparison_table, save_results


def benchmark_model(
    model_name: str,
    model_config: dict,
    chunks: list[dict],
    ground_truth: list[dict],
    chunking_strategy: str,
) -> dict:
    """Run the full benchmark for a single model."""
    print(f"\n{'=' * 60}")
    print(f"Benchmarking: {model_name}")
    print(f"  Model ID: {model_config['model_id']}")
    print(f"{'=' * 60}")

    print("  Loading model...")
    model, load_time = timed_call(load_model, model_config)
    print(f"  Model loaded in {load_time:.1f}s")

    chunk_texts = [chunk["text"] for chunk in chunks]
    print(f"  Embedding {len(chunk_texts)} chunks...")
    chunk_embeddings, embed_time = timed_call(embed_texts, model, chunk_texts, model_config)
    chunks_per_second = len(chunk_texts) / embed_time
    print(f"  Chunks embedded in {embed_time:.2f}s ({chunks_per_second:.1f} chunks/s)")

    queries = [row["query"] for row in ground_truth]
    print(f"  Embedding {len(queries)} queries...")
    query_embeddings, query_time = timed_call(embed_queries, model, queries, model_config)
    print(f"  Queries embedded in {query_time:.2f}s")

    print("  Computing retrieval metrics...")
    results = compute_retrieval_metrics(
        query_embeddings,
        chunk_embeddings,
        chunks,
        ground_truth,
        chunking_strategy=chunking_strategy,
    )
    embedding_dim = int(chunk_embeddings.shape[1])

    summary = {
        "model_name": model_name,
        "model_id": model_config["model_id"],
        "embedding_dim": embedding_dim,
        "load_time_s": round(load_time, 1),
        "embed_time_s": round(embed_time, 2),
        "chunks_per_second": round(chunks_per_second, 1),
        "query_time_s": round(query_time, 2),
        **results["averaged"],
        "per_query_results": results["per_query"],
    }

    print(f"\n  Results for {model_name}:")
    print(f"    Embedding dim:    {embedding_dim}")
    print(f"    Doc P@3:          {results['averaged']['doc_level_precision@3']:.3f}")
    print(f"    Doc P@5:          {results['averaged']['doc_level_precision@5']:.3f}")
    print(f"    Doc MRR:          {results['averaged']['doc_level_mrr']:.3f}")
    if results["averaged"]["chunk_level_recall@5"] is not None:
        print(f"    Chunk R@5:        {results['averaged']['chunk_level_recall@5']:.3f}")
        print(f"    Chunk MRR:        {results['averaged']['chunk_level_mrr']:.3f}")
        if results["averaged"]["chunk_level_ndcg@10"] is not None:
            print(f"    Chunk nDCG@10:    {results['averaged']['chunk_level_ndcg@10']:.3f}")
    print(f"    Embed speed:      {chunks_per_second:.1f} chunks/s")
    return summary


def _benchmark_all_models(
    chunks: list[dict],
    ground_truth: list[dict],
    strategy: str,
) -> list[dict]:
    """Benchmark every configured model and return successful results."""
    all_results: list[dict] = []
    for model_name, model_config in CANDIDATE_MODELS.items():
        try:
            result = benchmark_model(
                model_name,
                model_config,
                chunks,
                ground_truth,
                chunking_strategy=strategy,
            )
            result["chunking_strategy"] = strategy
            all_results.append(result)
        except Exception as exc:  # pragma: no cover - runtime robustness
            print(f"\n  ERROR benchmarking {model_name}: {exc}")
            import traceback

            traceback.print_exc()
    return all_results


def _run_models(strategy: str) -> tuple[list[dict], dict[str, dict]] | None:
    ground_truth = load_ground_truth()
    docs = load_documents()
    if not docs:
        print("ERROR: No documents found. Check EXTRACTED_TEXTS_DIR path.")
        return None

    chunks = build_chunks(docs, strategy=strategy)
    if not chunks:
        print("ERROR: No chunks built from input documents.")
        return None
    chunk_lookup = build_chunk_lookup(chunks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = _benchmark_all_models(chunks, ground_truth, strategy)
    return all_results, chunk_lookup


def run_benchmark(strategy: str, multi_run: bool = False) -> None:
    """Run benchmark for one strategy and persist outputs."""
    result = _run_models(strategy)
    if result is None:
        return
    all_results, chunk_lookup = result
    if all_results:
        print_comparison_table(all_results)
    save_results(all_results, chunk_lookup, strategy=strategy, multi_run=multi_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run embedding benchmark.")
    parser.add_argument(
        "--chunking-strategy",
        choices=["char", "paragraph"],
        default=CHUNKING_STRATEGY,
        help="Chunking strategy to use.",
    )
    parser.add_argument(
        "--suffix-by-strategy",
        action="store_true",
        help="Write benchmark outputs with a strategy suffix (e.g. _char, _paragraph).",
    )
    return parser.parse_args()


def run_cli(args: argparse.Namespace | None = None) -> None:
    """CLI entry point for embedding benchmark."""
    args = args or parse_args()
    run_benchmark(
        strategy=args.chunking_strategy,
        multi_run=args.suffix_by_strategy,
    )
