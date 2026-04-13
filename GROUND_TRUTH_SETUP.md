# Ground Truth Setup: Complete Guide

You now have **2-in-1 solution** for building ground truth datasets:

## Option 1: Simple DOI-based Seed Database (Quick)
For when you want a working dataset of articles on a topic with PDFs + metadata.

```bash
# Find and ingest 50 articles on vaccine-autism
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50
```

**Output:** 50 articles with:
- PDFs (where available)
- Metadata JSON (from PubMed, Crossref, OpenAlex)
- Ready for ingestion pipeline

**Best for:** Testing your full pipeline end-to-end

---

## Option 2: Parser Ground Truth (Recommended for Evaluation)
For evaluating parser quality with guaranteed text versions.

### Step 1: Generate List (2 minutes)

```bash
python -m eu_fact_force.ingestion.data_collection.free_ground_truth \
    --output-csv ground_truth_50_articles.csv
```

**Generates:** CSV with 50 articles (25 vaccine-autism + 25 other)
- All from **100% free sources** (PubMed Central + arXiv)
- Both PDF and text versions available
- No paywalls

```
ground_truth_50_articles.csv
├── article_id
├── doi
├── title
├── source (pubmed_central or arxiv)
├── text_format (pmc_xml or arxiv_source)
├── pdf_url
├── text_url
└── free_access (✓)
```

### Step 2: Download PDFs + Text (5-10 minutes)

```bash
python -m eu_fact_force.ingestion.data_collection.download_ground_truth \
    --csv ground_truth_50_articles.csv \
    --output-dir ./ground_truth_data \
    --workers 4
```

**Downloads:**
```
ground_truth_data/
├── pdf/              ← 50 PDF files
│   ├── PMC1234567.pdf
│   ├── PMC2345678.pdf
│   └── arxiv:2401.12345.pdf
├── text/             ← 50 ground truth text files
│   ├── PMC1234567.txt         (extracted from XML)
│   ├── PMC2345678.txt         (extracted from XML)
│   └── arxiv:2401.12345.txt   (extracted from LaTeX)
└── download_manifest.json
```

### Step 3: Evaluate Your Parser

```python
from eu_fact_force.ingestion.parsing import parse_pdf
import os

scores = []

for pdf_file in sorted(os.listdir('ground_truth_data/pdf/')):
    article_id = pdf_file.replace('.pdf', '')

    # Parse PDF
    pdf_path = f'ground_truth_data/pdf/{pdf_file}'
    extracted_text = parse_pdf(pdf_path)

    # Load ground truth
    gt_path = f'ground_truth_data/text/{article_id}.txt'
    ground_truth = open(gt_path).read()

    # Compare
    similarity = compute_similarity(extracted_text, ground_truth)
    scores.append((article_id, similarity))

# Report
for article_id, score in scores:
    print(f"{article_id}: {score:.1%}")

print(f"\nAverage: {sum(s for _, s in scores) / len(scores):.1%}")
```

**Best for:** Measuring parser quality on real documents

---

## Key Differences

| Aspect | Option 1: Seed DB | Option 2: Ground Truth |
|--------|------------------|----------------------|
| **Purpose** | Full pipeline testing | Parser quality evaluation |
| **Speed** | 15-20 min | 7-12 min |
| **Text versions** | Only if extracted by parser | Guaranteed (XML/LaTeX) |
| **Sources** | All academic APIs | PMC + arXiv only |
| **Cost** | Free | Free |
| **Best for** | End-to-end testing | Parser benchmarking |

---

## What's Available

### Scripts

1. **`seed_db.py`** — Full pipeline (search + ingest articles)
   - Commands: `search`, `ingest`, `full`
   - Input: Topic query
   - Output: PDFs + metadata JSON

2. **`free_ground_truth.py`** — Find articles with text versions
   - Searches PMC + arXiv
   - Returns CSV with download URLs
   - Guaranteed free access, text available

3. **`download_ground_truth.py`** — Download PDFs + extract text
   - Downloads from URLs in CSV
   - Extracts text from PMC XML / arXiv LaTeX
   - Parallel downloads (4 workers default)

4. **`search.py`** — Core search module
   - `PubMedSearcher`
   - `CrossrefSearcher`
   - `ArticleSearcher`

5. **`batch_ingest.py`** — Batch ingest from search results
   - Fetches metadata from 5 sources
   - Downloads PDFs
   - Tracks success/failure

### Documentation

- **`SEED_DB_GUIDE.md`** — Comprehensive seed database guide
- **`QUICKSTART.md`** — 5-minute quick start (seed DB)
- **`GROUND_TRUTH_COLLECTION.md`** — Ground truth setup guide
- **`SEED_DB.md`** — Detailed technical docs

### Tests

- **`test_seed_db_search.py`** — Integration tests

---

## Recommended Workflow

### For Parsing Evaluation (Most Common)

```bash
# 1. Generate list of 50 articles (with text versions available)
python -m eu_fact_force.ingestion.data_collection.free_ground_truth \
    --output-csv ground_truth_50_articles.csv

# 2. Download PDFs and text versions
python -m eu_fact_force.ingestion.data_collection.download_ground_truth \
    --csv ground_truth_50_articles.csv \
    --output-dir ./ground_truth_data

# 3. Run your parser evaluation
python your_parser_evaluation.py \
    --pdf-dir ./ground_truth_data/pdf \
    --text-dir ./ground_truth_data/text \
    --output-report parser_quality_report.json
```

### For Full Pipeline Testing

```bash
# 1. Search and ingest articles
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50

# 2. Run through ingestion pipeline
python -m eu_fact_force.ingestion.run_pipeline \
    --source-dir ./vaccine_autism_seed/json \
    --pdf-dir ./vaccine_autism_seed/pdf

# 3. Evaluate embeddings
python your_search_evaluation.py \
    --index-dir ./vaccine_autism_seed/embeddings
```

---

## Free Sources Explained

### PubMed Central (PMC)
- **What:** Free, full-text biomedical articles
- **Coverage:** 100% of articles are open access
- **Text format:** Official XML (very clean)
- **Quality:** Published peer-reviewed articles
- **Size:** ~4 million articles
- **Access:** Free (API)

### arXiv
- **What:** Preprints in physics, math, CS, bio, etc.
- **Coverage:** Unlimited access to source files
- **Text format:** LaTeX source (original format)
- **Quality:** Pre-publication, peer-review varies
- **Size:** ~2.3 million papers
- **Access:** Free (API)

Both are **100% free, no paywalls, no registration required**.

---

## Common Issues & Solutions

### "No PDFs downloaded"

Some articles don't have downloadable PDFs (metadata only).

```bash
# Use --skip-pdf flag for faster processing
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./output \
    --max-articles 50 \
    --skip-pdf
```

### "Text extraction quality is poor"

For arXiv papers, LaTeX extraction includes math formulas. Clean them:

```python
import re

text = open('ground_truth_data/text/arxiv_paper.txt').read()

# Remove math
text = re.sub(r'\$[^\$]+\$', '[FORMULA]', text)

# Remove excessive whitespace
text = re.sub(r'\s+', ' ', text)

open('cleaned.txt', 'w').write(text)
```

### "Download is slow"

Increase worker threads:

```bash
python -m eu_fact_force.ingestion.data_collection.download_ground_truth \
    --csv ground_truth_50_articles.csv \
    --output-dir ./ground_truth_data \
    --workers 8  # Default is 4
```

### "Some articles still failed to download"

This is normal. Check the manifest:

```bash
cat ground_truth_data/download_manifest.json | python -m json.tool | grep -A 5 "failed"
```

Expected: ~45-48 successful out of 50 (90-96% success rate).

---

## Architecture

```
eu_fact_force/ingestion/data_collection/
├── search.py                           ← API search logic
├── batch_ingest.py                     ← Batch ingest
├── seed_db.py                          ← CLI orchestrator
├── free_ground_truth.py                ← Ground truth search
├── download_ground_truth.py            ← Download + extract
├── SEED_DB.md                          ← Detailed docs
├── SEED_DB_GUIDE.md                    ← Comprehensive guide
└── GROUND_TRUTH_COLLECTION.md          ← Ground truth docs

tests/ingestion/
└── test_seed_db_search.py              ← Tests
```

---

## Next Steps

**Choose one:**

1. **Quick test** → Run `seed_db full` command (15 min)
2. **Parsing evaluation** → Run both `free_ground_truth` + `download_ground_truth` (12 min)
3. **Full pipeline** → Run `seed_db full` then your ingestion pipeline (30 min)

All are completely **free and paywall-free**.

---

## Questions?

- **Quick start:** See `QUICKSTART.md`
- **Seed DB details:** See `SEED_DB_GUIDE.md`
- **Ground truth setup:** See `GROUND_TRUTH_COLLECTION.md`
- **Technical details:** See `SEED_DB.md`

All tools use APIs that are **100% free, no authentication required** (except optional email for PubMed).
