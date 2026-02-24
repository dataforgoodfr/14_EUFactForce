# Parsing Benchmark

Exploration and comparison of PDF parsing methods/tools (LlamaParse, PyMuPDF) on a diverse set of documents.

## Structure

```
parsing/
├── benchmark.py          # Run PDF parsing benchmarks (speed, volume, metadata)
├── pdf_cleaner.py        # PDF pre-processing (crop headers/footers, redact figures, linearize columns; profile-aware)
├── text_cleaning.py      # Text post-processing (fix encoding, rejoin hyphens, remove noise; opt-in profiles)
├── quality_scoring.py    # Orchestrate quality evaluation across all scoring dimensions
├── fidelity_optimization.py # Baseline leaderboard, taxonomy, matrix, routing, regression gates
│
├── scoring/              # Scoring sub-modules
│   ├── content.py        # Content presence scoring (title, authors, DOI, abstract, ...)
│   ├── metadata.py       # Metadata accuracy scoring
│   ├── similarity.py     # Reference-text similarity scoring
│   └── utils.py          # Shared utilities (fuzzy matching, normalization)
│
├── data/                 # PDF documents (original + processed variants)
│   ├── document_diversity/       # Original PDFs
│   ├── document_diversity_clean/ # Cleaned (cropped + figures redacted)
│   └── document_diversity_column/# Column-linearized variants
│
├── ground_truth/         # Reference data for scoring
│   ├── ground_truth.json # Per-document annotations (title, authors, key passages, ...)
│   ├── README.md         # Canonical editorial standard for full-text ground truth
│   └── texts/            # Human-written reference texts for similarity scoring
│
└── output/               # Generated outputs (CSV results + extracted texts)
    ├── extracted_texts/   # Cached text extractions per (document, parser_config)
    ├── benchmark_results_extended.csv
    └── quality_scores.csv # Includes applicability-aware content score (%)
```

## Usage

All scripts are run from the `ingestion/parsing/` directory.

```bash
# 1. Pre-process PDFs (crop, redact figures, linearize columns)
python pdf_cleaner.py --profile default

# 2. Run parsing benchmark (requires LLAMA_CLOUD_API_KEY in .env)
python benchmark.py [original|clean|column|both|all] [--no-cache]

# 3. Evaluate extraction quality (auto-discovers parser configs by extracted files)
python quality_scoring.py --discover-configs

# 4. Build baseline leaderboard artifacts
python fidelity_optimization.py baseline

# 5. Build deterministic error taxonomy (includes LLM-eye ambiguity tagging)
python fidelity_optimization.py taxonomy

# 6. Build optimization matrix and ranking
python fidelity_optimization.py matrix

# 7. Recommend parser routing by doc_type
python fidelity_optimization.py routing

# 8. Evaluate regression gates against baseline
python fidelity_optimization.py gates
```

`gates` is optional during exploration and useful at promotion time. Run it
when you are about to adopt a candidate setup (for example before updating
routing defaults or promoting a new baseline) to ensure no unintended quality
regression.

## Ground-Truth Standard

Ground-truth full-text files are normalized with a documented editorial policy
(footnotes handling, marker consistency, order conventions, etc.). The canonical
reference is:

- `ground_truth/README.md`

## Environment

Requires the `parsing` dependency group:

```bash
uv sync --group parsing
```

A `.env` file with `LLAMA_CLOUD_API_KEY=<your-key>` is needed for LlamaParse benchmarks.
