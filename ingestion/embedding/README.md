# Embedding Model Benchmark

Evaluates multilingual embedding models for the EU Fact Force semantic search pipeline.

## Goal

Select the best open-source, multilingual embedding model to convert article chunks into vectors for similarity search. The model must handle French and English scientific text, run on CPU (no paid APIs), and produce embeddings suitable for storage in a vector database (Qdrant or pgvector).

## Candidate Models

| Model | Dimensions | Max tokens | Size | Notes |
|-------|-----------|------------|------|-------|
| `intfloat/multilingual-e5-base` | 768 | 512 | ~1.1 GB | Mentioned in project FAQ, good baseline |
| `BAAI/bge-m3` | 1024 | 8192 | ~2.3 GB | Top MTEB multilingual retrieval, dense + sparse |
| `sentence-transformers/LaBSE` | 768 | 256 | ~1.8 GB | Strong cross-language, but short context |

## Metrics

- **Doc-level Precision@k / MRR**: Coarse retrieval quality against `relevant_docs`
- **Chunk-level Recall@k / MRR**: Passage retrieval quality against `relevant_chunk_ids_by_strategy`
- **Chunk-level nDCG@10** (when graded labels exist): Ranking quality for `high` vs `partial`
- **Cross-language retrieval**: FR query -> EN document and vice versa
- **Embedding speed**: Chunks/second on CPU
- **Vector dimensions**: Storage and search performance impact

## Latest Results (Current Baseline)

Run context:
- Corpus: 10 documents split into 851 chunks (`strategy=char`, `chunk_size=1200`, `overlap=200`) and 1004 chunks (`strategy=paragraph`, `chunk_size=1200`, `overlap=200`)
- Queries: 12 queries from `ingestion/embedding/data/ground_truth.json`
- Retrieval: chunk similarity with doc-level relevance evaluation (baseline run)

| Model | Dim | P@3 | P@5 | MRR | Speed (chunks/s) | Load (s) |
|-------|-----|-----|-----|-----|------------------|----------|
| `multilingual-e5-base` | 768 | 0.736 | 0.806 | **0.792** | 25.8 | 87.6 |
| `bge-m3` | 1024 | 0.736 | **0.847** | 0.778 | 8.0 | 167.5 |
| `LaBSE` | 768 | 0.597 | 0.826 | 0.778 | **35.1** | 97.2 |

Cross-language first relevant rank (lower is better):
- `multilingual-e5-base`: EN 1.6 | FR 1.7
- `bge-m3`: EN 1.6 | FR 1.3
- `LaBSE`: EN 1.7 | FR 2.0

## Updated Evaluation Design

The benchmark now supports a 2-tier evaluation:

- **Tier 1 (doc-level)**: model screening with `relevant_docs`
- **Tier 2 (chunk-level)**: passage quality with `relevant_chunk_ids_by_strategy` and optional `relevant_chunk_labels_by_strategy`

Ground-truth schema:

- required fields: `query`, `lang`, `relevant_docs`
- strategy-aware manual optional fields: `relevant_chunk_ids_by_strategy`, `relevant_chunk_labels_by_strategy`
- weak-label optional fields: `weak_chunk_labels_by_strategy`, `weak_label_metadata`

When `relevant_chunk_ids_by_strategy` is present, benchmark evaluation automatically
selects the labels that match the active chunking strategy (`char` or `paragraph`).

During benchmark evaluation, label priority is:

1. manual graded labels (`relevant_chunk_labels_by_strategy`)
2. manual binary labels (`relevant_chunk_ids_by_strategy`)
3. weak labels (`weak_chunk_labels_by_strategy`)

### What weak labeling means

Weak labeling is an automated way to assign approximate relevance labels to
chunks when full manual annotation is not available yet.

- A query/chunk pair receives a tentative label: `high`, `partial`, or `irrelevant`
- Labels are inferred from heuristic signals (dense retrieval rank, lexical overlap, anchor passage hits, plus sampled negatives)
- Each weak label includes:
  - `confidence`: numeric score used to derive the final label
  - `sources`: which signals contributed (for traceability)
- Weak labels are useful for rapid benchmarking and bootstrapping, but they are not a substitute for gold human labels

When chunk labels are present, benchmark output includes:

- `chunk_level_recall@1,@3,@5,@10`
- `chunk_level_mrr`
- `chunk_level_ndcg@10` (graded-only)

For annotation workflow, see:

- `ingestion/embedding/data/ANNOTATION_GUIDELINES.md`
- generated candidate pool: `ingestion/embedding/output/chunk_judging_pool.json`

## Data

Uses the 10 parsed documents from `ingestion/parsing/output/extracted_texts/` (LlamaParse markdown variants).

## Remaining Work

- Add a small manually validated chunk set per strategy to better calibrate weak-label thresholds.
- Add tests for benchmark CLI output naming behavior with and without `--suffix-by-strategy`.
- Add a short script or make target to run `char` and `paragraph` sequentially and produce a single delta report.
- Re-run and refresh the "Latest Results" table after major corpus or ground-truth updates.
- Define a policy for versioning generated artifacts (`output/*.json`, `output/*.csv`) vs keeping them ignored.

## Usage

```bash
# From repo root
uv sync --group embedding

# Run the benchmark (default: paragraph chunks)
python3 ingestion/embedding/benchmark.py

# Run char chunking explicitly
python3 ingestion/embedding/benchmark.py --chunking-strategy char

# Keep both strategy outputs side-by-side (adds _char/_paragraph suffixes)
python3 ingestion/embedding/benchmark.py --chunking-strategy char --suffix-by-strategy
python3 ingestion/embedding/benchmark.py --chunking-strategy paragraph --suffix-by-strategy

# Auto-generate weak labels on corpus (writes updated ground truth)
python3 ingestion/embedding/benchmark.py --generate-weak-labels --weak-label-strategy paragraph --write-output ingestion/embedding/data/ground_truth.json

# Optional: use the CLI default weak-label strategy (currently char)
python3 ingestion/embedding/benchmark.py --generate-weak-labels --write-output ingestion/embedding/data/ground_truth.json
```

Outputs:

- `ingestion/embedding/output/embedding_benchmark_results.json`
- `ingestion/embedding/output/embedding_benchmark_summary.csv`
- `ingestion/embedding/output/chunk_judging_pool.json`

When running with `--suffix-by-strategy` (recommended for side-by-side strategy comparisons), outputs are saved with suffixes:

- `ingestion/embedding/output/embedding_benchmark_results_char.json`
- `ingestion/embedding/output/embedding_benchmark_results_paragraph.json`
- `ingestion/embedding/output/embedding_benchmark_summary_char.csv`
- `ingestion/embedding/output/embedding_benchmark_summary_paragraph.csv`
- `ingestion/embedding/output/chunk_judging_pool_char.json`
- `ingestion/embedding/output/chunk_judging_pool_paragraph.json`

Weak-label generation output:

- updated ground truth JSON at `--write-output` path
- calibration report: `ingestion/embedding/output/weak_label_calibration_report_<strategy>.json`