# Chunk Relevance Annotation Guidelines

This guide defines how to annotate chunk relevance for `ingestion/embedding/data/ground_truth.json`.

## Goal

Evaluate embedding retrieval at passage level without labeling every chunk in the corpus.

## Pooling Protocol

- For each query, use the benchmark-generated pool from `ingestion/embedding/output/chunk_judging_pool.json`.
- Judge only pooled candidates:
  - union of top-k chunks across benchmarked models
  - plus random negatives
- Do not exhaustively scan all corpus chunks.

## Label Scheme

Use strategy-specific `relevant_chunk_labels_by_strategy` with one of:

- `high`: direct, strong support for the query intent.
- `partial`: related evidence, but weaker, indirect, or incomplete support.
- `irrelevant`: off-topic or non-supporting for this query.

Binary relevance (`relevant_chunk_ids_by_strategy`) is derived from labels where gain > 0 (`high` and `partial`).

Use strategy-specific fields:

- `relevant_chunk_ids_by_strategy.char` / `.paragraph`
- `relevant_chunk_labels_by_strategy.char` / `.paragraph`

This avoids penalizing alternative chunkers when chunk boundaries differ.

## Weak Labels And Manual Labels

- Weak labels are stored under `weak_chunk_labels_by_strategy` and include:
  - `chunk_id`, `label`, `confidence`, `sources`
- Manual labels remain authoritative.
- Conflict resolution in benchmark:
  1. manual graded labels (`relevant_chunk_labels_by_strategy`)
  2. manual binary labels (`relevant_chunk_ids_by_strategy`)
  3. weak labels
- Use weak labels to bootstrap coverage, then replace high-impact queries with manual labels.

## Quality Rules

- Judge the chunk text as shown, not the full source document.
- Favor semantic relevance over exact keyword overlap.
- For multilingual queries, cross-language supporting chunks are valid.
- If two chunks are near-duplicates, prefer labeling one as `high` and the duplicate as `partial`.
- Keep decisions consistent across EN/FR query pairs when intent is equivalent.
