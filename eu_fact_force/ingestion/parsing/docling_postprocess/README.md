# Docling Postprocess

This package contains Docling-specific cleanup logic used by the parsing benchmark.
It runs inside `parse_docling()` and is exposed through one public function:

- `render_docling_output(...)` in `__init__.py`

## Why this exists

Docling output can include:

- ghost text blocks whose bbox has no real PDF words
- OCR-like text inside figure regions
- inline footnote blocks that harm body alignment
- heading depth variations that differ from ground-truth editorial style

The goal is to improve extraction fidelity for scoring while keeping behavior deterministic.

## Processing flow

`render_docling_output(...)` runs this sequence:

1. Export Docling text (`text` or `markdown` mode)
2. Normalize markdown headings to level-1 (`markdown.py`)
3. Optionally run bbox validation (`ghost_filter.py`)
   - detect ghost text blocks
   - remove dropped snippets conservatively (`cleanup.py`)
4. Relocate labeled footnotes to trailing section (`footnotes.py`)
5. Return `(full_text, stats)`

## Module map

- `constants.py`: thresholds and heuristic constants
- `geometry.py`: bbox/rect conversions and overlap helpers
- `ghost_filter.py`: PDF-word agreement checks and block dropping logic
- `cleanup.py`: remove dropped snippets from rendered output
- `footnotes.py`: footnote extraction/relocation helpers
- `markdown.py`: heading normalization for GT compatibility

## Key thresholds and intent

- `DOCLING_PICTURE_OVERLAP_DROP_RATIO = 0.6`  
  A provenance box is considered inside a picture region at 60% overlap.

- `DOCLING_PICTURE_OVERLAP_BLOCK_RATIO = 0.5`  
  Drop a non-caption text block if at least half of its provenance boxes are inside picture regions.

- `DOCLING_PYMUPDF_MIN_TOKEN_OVERLAP_RATIO = 0.2`  
  Require minimum token agreement between Docling text and PDF words in the same bbox.

- `DOCLING_SMALL_BOX_MAX_AREA_RATIO = 0.0015`  
  Tiny bboxes are treated as high-risk noise and removed more conservatively.

## Trade-offs

- Aggressive dropping improves precision but can remove valid small text.
- Conservative dropping keeps recall but may retain noisy OCR artifacts.
- Line-scoped snippet removal avoids broad accidental deletions but may leave
  some embedded ghost fragments untouched.
- Footnote relocation helps body similarity but can affect metadata-style cues.

## How to tune safely

From repo root, run (e.g.):

```bash
python benchmark.py raw --configs docling_markdown --no-cache
python quality_scoring.py --configs docling_markdown --timing-output-csv output/analysis/docling_timing.csv
```

`docling_markdown` includes indexing-focused cleanup by default.

Compare before/after at least:

- `text_similarity`
- `content_precision` and `content_recall`
- `structural_quality`
- `meta_accuracy_score`

If changing constants, prefer one change at a time and keep result snapshots in `output/analysis/`.
