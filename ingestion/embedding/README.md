# Embedding Model Benchmark

Evaluates multilingual embedding models for the EU Fact Force semantic search pipeline.

## Goal

Select the best open-source, multilingual embedding model to convert article chunks into vectors for similarity search. The model must handle French and English scientific text, run on CPU (no paid APIs), and produce embeddings suitable for storage in a vector database (Qdrant or pgvector).

## Model

Current benchmark baseline is pinned to:

| Model | Dimensions | Max tokens | Size | Notes |
|-------|-----------|------------|------|-------|
| `intfloat/multilingual-e5-base` | 768 | 512 | ~1.1 GB | Selected baseline for current PR scope |

## Metrics

- **Precision@5 / Precision@10**: Of top results, how many are relevant?
- **MRR (Mean Reciprocal Rank)**: How high does the first relevant result appear?
- **Cross-language retrieval**: FR query → EN document and vice versa
- **Embedding speed**: Chunks/second on CPU
- **Vector dimensions**: Storage and search performance impact

## Latest Results (Baseline)

Run context:
- Corpus: 10 documents split into 851 chunks (`chunk_size=1200`, `overlap=200`)
- Queries: 12 queries from `ingestion/embedding/data/ground_truth.json`
- Retrieval: chunk similarity with doc-level relevance evaluation

| Model | Dim | P@3 | P@5 | MRR | Speed (chunks/s) | Load (s) |
|-------|-----|-----|-----|-----|------------------|----------|
| `multilingual-e5-base` | 768 | 0.736 | 0.806 | **0.792** | 25.8 | 87.6 |

Evaluation caveat:
- `ground_truth.json` is currently **doc-level** (`relevant_docs`), while retrieval is **chunk-level**.
- This is still useful for coarse model comparison, but it does not verify that the returned chunk is the best supporting passage.
- Next upgrade: keep doc-level labels and add chunk-level labels (`relevant_chunk_ids`) to report chunk-native metrics.

## Usage

```bash
# From repo root
uv sync --group embedding

# Run the benchmark
python ingestion/embedding/benchmark.py
```

## Data

Uses the 10 parsed documents from `ingestion/parsing/output/extracted_texts/` (LlamaParse markdown variants).
