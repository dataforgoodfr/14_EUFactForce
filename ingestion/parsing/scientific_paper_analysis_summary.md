# Scientific-Paper Parsing Analysis Summary

This file is the durable summary of scientific-paper Docling analysis outcomes.
Generated artifacts live under `output/analysis/` and are intentionally gitignored.

## Scope

- Dataset slice: `doc_type = scientific_paper` (6 files)
- Parser configs: `docling_markdown`, `docling_postprocess_markdown`
- Comparison basis: `after - baseline`

## Run Settings (Baseline vs Current)

Baseline run:
- Command: `python quality_scoring.py --doc-type scientific_paper --configs docling_markdown,docling_postprocess_markdown --timing-output-csv output/analysis/scientific_paper_docling_timing_baseline.csv`
- Body cleanup used for similarity: TOC strip + explicit references heading strip + footnotes strip + legal boilerplate strip + trailing citation-noise trim.
- Limitation: when extraction had no explicit `References` heading, many reference-like lines could remain in extracted body.

Current run:
- Command: `python quality_scoring.py --doc-type scientific_paper --configs docling_markdown,docling_postprocess_markdown --timing-output-csv output/analysis/scientific_paper_docling_timing_after.csv`
- Added logic: **implicit references catch** in `scoring/utils.py::strip_references_section()`.
- New behavior: if the latter part of text is reference-dense (DOI/URL/arXiv/numbered citation patterns), those lines are removed even without an explicit `References` header.

## Current Results

Average delta across scientific-paper files (`current - baseline`):

| parser_config | similarity | precision | order | structural_quality | metadata_score | row_runtime_ms |
|---|---:|---:|---:|---:|---:|---:|
| `docling_markdown` | +0.0582 | +0.0738 | +0.0017 | +1.1333 | -1.6167 | -867.45 |
| `docling_postprocess_markdown` | +0.0582 | +0.0738 | +0.0017 | +1.1333 | -1.6167 | -880.16 |

Scientific-paper aggregate metrics after implicit reference cleanup:

- Similarity: `0.895`
- Recall: `0.947`
- Precision: `0.956`
- Order: `0.949`

## Key Interpretation

- Main improvement comes from symmetric handling of implicit references/citation tails.
- `pnas.201912444` shifted from artificially low similarity to high alignment after cleanup.
- Structural quality improved with no order regression.
- Metadata accuracy remains slightly lower and should be tuned separately if needed.
