# Parsing Benchmark

Exploration and comparison of PDF parsing methods/tools (LlamaParse, PyMuPDF) on a diverse set of documents.

## Structure

```
parsing/
├── benchmark.py          # Run PDF parsing benchmarks (speed, volume, metadata)
├── pdf_cleaner.py        # PDF pre-processing (crop headers/footers, redact figures, linearize columns)
├── text_cleaning.py      # Text post-processing (fix encoding, rejoin hyphens, remove noise)
├── quality_scoring.py    # Orchestrate quality evaluation across all scoring dimensions
├── benchmarking/         # Benchmarking domain modules (parsers, configs, storage, GT)
│
├── scoring/              # Scoring sub-modules
│   ├── content.py        # Content presence scoring (title, authors, DOI, abstract, ...)
│   ├── metadata.py       # Metadata accuracy scoring
│   ├── similarity.py     # Reference-text similarity scoring
│   └── utils.py          # Shared utilities (fuzzy matching, normalization)
│
├── data/                 # PDF documents (raw + processed variants)
│   ├── document_diversity/       # Raw PDFs
│   ├── document_diversity_clean/ # Preprocessed (cropped + figures redacted)
│   └── document_diversity_column/# Column-linearized variants
│
├── ground_truth/         # Reference data for scoring
│   ├── ground_truth.json # Per-document annotations (title, authors, key passages, ...)
│   └── texts/            # Human-written reference texts for similarity scoring
│
└── output/               # Generated outputs (CSV results + extracted texts)
    ├── extracted_texts/   # Cached text extractions (structured by dataset variant)
    │   ├── raw/<parser_config>/<document_stem>.txt
    │   ├── preprocessed/<parser_config>/<document_stem>.txt
    │   └── column/<parser_config>/<document_stem>.txt
    ├── benchmark_results_extended.csv
    └── quality_scores.csv
```

## Usage

All scripts are run from the `ingestion/parsing/` directory.

```bash
# 1. Pre-process PDFs (crop, redact figures, linearize columns)
python pdf_cleaner.py

# 2. Run parsing benchmark (requires LLAMA_CLOUD_API_KEY in .env)
python benchmark.py [raw|preprocessed|column|all] [--preprocessed] [--column] [--no-cache]
# Default: raw only
# Additive options: --preprocessed and/or --column
# Parser profile default is now `fast` (pruned set for speed).
# Optional doc-type filter from ground truth:
#   --doc-type scientific_paper
# Profiles available:
#   --profile full|fast|docling_only
# Or provide explicit config list:
#   --configs "pymupdf,docling_markdown,llamaparse_markdown"
# Retrieval-focused Docling export (cleaner indexing text):
#   --configs "docling_markdown_indexing"
# Legacy aliases are still accepted (e.g. docling_postprocess_markdown, *_clean),
# but canonical names are docling_markdown_indexing and *_preprocessed.
# New extraction outputs are written under output/extracted_texts/{raw|preprocessed|column}/...

# 3. Evaluate extraction quality
python quality_scoring.py
# Quality scoring profile default is now `fast`.
# Same pruning controls are available:
#   python quality_scoring.py --profile fast
#   python quality_scoring.py --filename BEUC-X-2025-113_Influencer_Marketing_Unboxed_Report.pdf --profile docling_only
# Optional doc-type filtering + per-row timing CSV:
#   python quality_scoring.py --doc-type scientific_paper --configs docling_markdown,docling_markdown_indexing --timing-output-csv output/analysis/scientific_timing.csv
# Timing diagnostics:
#   python quality_scoring.py --profile fast --log-timing --timing-threshold-ms 500
# Optional speed mode (skip expensive similarity metrics):
#   python quality_scoring.py --profile fast --skip-similarity

# 4. Quickly rank variants for one document (fast mode by default)
python score_single_file.py BEUC-X-2025-113_Influencer_Marketing_Unboxed_Report.pdf --parser-prefix docling
# Optional slower full fidelity metrics:
# python score_single_file.py BEUC-X-2025-113_Influencer_Marketing_Unboxed_Report.pdf --parser-prefix docling --mode full
```

## Scientific-Paper Optimization Loop

Use this loop when tuning Docling quality specifically for `scientific_paper` documents:

```bash
# 1) Refresh scientific-paper Docling extractions with runtime metrics
python benchmark.py raw --doc-type scientific_paper --configs docling_markdown,docling_markdown_indexing --no-cache

# 2) Score only scientific papers and export per-row timing
python quality_scoring.py --doc-type scientific_paper --configs docling_markdown,docling_markdown_indexing --timing-output-csv output/analysis/scientific_paper_docling_timing.csv

# 3) Optional quick smoke validation across fast profile (without heavy similarity)
python quality_scoring.py --profile fast --skip-similarity
```

Recommended outputs to keep for iteration tracking:
- `output/analysis/scientific_paper_docling_baseline.csv`
- `output/analysis/scientific_paper_docling_after.csv`
- `output/analysis/scientific_paper_docling_changelog.csv`

## Environment

Requires the `parsing` dependency group:

```bash
uv sync --group parsing
```

A `.env` file with `LLAMA_CLOUD_API_KEY=<your-key>` is needed for LlamaParse benchmarks.
