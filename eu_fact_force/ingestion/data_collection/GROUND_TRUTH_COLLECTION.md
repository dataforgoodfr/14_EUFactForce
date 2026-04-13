# Ground Truth Collection: 50 Free Articles with PDF + Text

Build a ground truth dataset of 50 articles (25 vaccines-autism + 25 other biomedical) where you have both:
- **PDF file** (original document)
- **Text version** (for comparison/validation)

All from **100% free sources** (no paywalls).

## Overview

```
Step 1: Search
  ↓
  Collect 50 articles from:
  - PubMed Central (free, OA subset)
  - arXiv (free preprints)
  ↓
  Output: ground_truth_50_articles.csv

Step 2: Download
  ↓
  Download PDFs + text versions
  ↓
  Output: ground_truth_data/
    ├── pdf/        (50 PDFs)
    └── text/       (50 text files)
```

## Quick Start

### Step 1: Generate List of 50 Articles

```bash
python -m eu_fact_force.ingestion.data_collection.free_ground_truth \
    --output-csv ground_truth_50_articles.csv
```

Takes 1-2 minutes. Output:
```
ground_truth_50_articles.csv
  ├── 25 vaccine-autism articles (20 from PMC + 5 from arXiv)
  └── 25 other biomedical articles (20 from PMC + 5 from arXiv)
```

Inspect the CSV:
```bash
head -10 ground_truth_50_articles.csv
cat ground_truth_50_articles.csv | wc -l  # Should be 51 (header + 50 rows)
```

### Step 2: Download PDFs + Text Versions

```bash
python -m eu_fact_force.ingestion.data_collection.download_ground_truth \
    --csv ground_truth_50_articles.csv \
    --output-dir ./ground_truth_data \
    --workers 4
```

Takes 5-10 minutes (depends on internet). Output:
```
ground_truth_data/
├── pdf/                      (50 PDF files)
│   ├── PMC1234567.pdf       ← PubMed Central articles
│   ├── PMC2345678.pdf
│   └── arxiv:2401.12345.pdf ← arXiv preprints
├── text/                     (50 text files)
│   ├── PMC1234567.txt       ← Extracted from XML
│   ├── PMC2345678.txt
│   └── arxiv:2401.12345.txt ← Extracted from LaTeX
└── download_manifest.json    (success/failure log)
```

## What You Get

### PDF Files
- **PubMed Central PDFs**: Original published PDFs (high quality)
- **arXiv PDFs**: Preprint PDFs (good quality)
- All are downloadable without payment

### Text Versions (Ground Truth)

**For PMC articles:** Text extracted from official XML
- High quality, structured
- Contains: title, abstract, body, references
- Format: Markdown-like text

**For arXiv articles:** Text extracted from LaTeX source
- Source-level extraction
- Most accurate representation of paper structure
- Includes: title, abstract, sections, math

## Understanding the Output

### `ground_truth_50_articles.csv`

```csv
category,article_id,doi,title,source,text_format,pdf_url,text_url,free_access
vaccine_autism,PMC1234567,10.1234/example,"Title of article",pubmed_central,pmc_xml,https://...,https://...,✓
vaccine_autism,arxiv:2401.12345,,arXiv paper title,arxiv,arxiv_source,https://...,https://...,✓
...
```

### Directory Structure

```
ground_truth_data/
├── pdf/
│   ├── PMC1234567.pdf         (2.5 MB)
│   ├── PMC2345678.pdf         (1.8 MB)
│   └── arxiv:2401.12345.pdf   (0.9 MB)
├── text/
│   ├── PMC1234567.txt         (45 KB, extracted from XML)
│   ├── PMC2345678.txt         (38 KB, extracted from XML)
│   └── arxiv:2401.12345.txt   (52 KB, extracted from LaTeX)
└── download_manifest.json
```

## Using for Parser Evaluation

### 1. Test PDF Parsing

Use your parser on PDF files:
```python
from eu_fact_force.ingestion.parsing import parse_pdf

for pdf_file in os.listdir('ground_truth_data/pdf/'):
    pdf_path = f'ground_truth_data/pdf/{pdf_file}'
    extracted_text = parse_pdf(pdf_path)

    # Compare with ground truth
    article_id = pdf_file.replace('.pdf', '')
    ground_truth = open(f'ground_truth_data/text/{article_id}.txt').read()

    similarity = compute_similarity(extracted_text, ground_truth)
    print(f"{article_id}: {similarity:.2%} match")
```

### 2. Measure Parser Quality

Metrics you can compute:
- **Similarity**: How much of the ground truth is in parsed output
- **Precision**: Of what was extracted, how much is correct
- **Completeness**: How much of the article was extracted
- **Structure preservation**: Are sections, paragraphs preserved

Example:
```python
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

for article_id in articles:
    pdf_text = open(f'ground_truth_data/pdf/{article_id}.pdf').read()
    gt_text = open(f'ground_truth_data/text/{article_id}.txt').read()

    pdf_embedding = model.encode(pdf_text)
    gt_embedding = model.encode(gt_text)

    similarity = cosine_similarity([pdf_embedding], [gt_embedding])[0][0]
    print(f"{article_id}: {similarity:.3f}")
```

## Article Distribution

### Vaccine-Autism Articles (25)

**From PubMed Central (20):**
- Recent clinical studies on vaccine safety
- Meta-analyses of vaccine efficacy
- Epidemiological studies
- All peer-reviewed, published

**From arXiv (5):**
- Recent biomedical preprints
- May include reviews or analyses
- Pre-publication versions

### Other Biomedical Articles (25)

**From PubMed Central (20):**
- Randomized controlled trials
- Meta-analyses
- Clinical research studies
- Various specialties (not vaccine-related)

**From arXiv (5):**
- Biomedical preprints
- Quantitative biology
- Medical physics

## Customization

### Change the queries

Edit the search methods in `free_ground_truth.py`:
```python
def search_pmc_vaccine_autism(self, limit: int = 30):
    query = '(YOUR QUERY HERE) AND (additional filters)'
    # ...
```

### Change the limits

```bash
# Collect 40 articles instead of 50
python free_ground_truth.py --output-csv my_articles.csv
# Then edit and run only the first 40 rows of CSV
```

### Use different sources

The scripts support:
- **PubMed Central** — Published peer-reviewed articles (best quality)
- **arXiv** — Preprints (good for supplemental data)
- **bioRxiv/medRxiv** — Biological/medical preprints (would need implementation)

## Troubleshooting

### "Download failed" errors

Some articles may not have downloadable versions at the URLs. This is normal - you'll get ~45-48 successful downloads out of 50.

```bash
# Check manifest
cat ground_truth_data/download_manifest.json | jq '.successful'
```

### Large file sizes

PMC PDFs can be 2-5 MB each. Total expected: 75-150 MB for 50 articles.

### Text extraction quality

- **PMC XML**: High quality (structured, official)
- **arXiv LaTeX**: Good quality (source-level), but may include math formulas as text

For matcher evaluation, you may want to:
1. Clean up LaTeX math: remove `$...$` or replace with `[FORMULA]`
2. Normalize whitespace and special characters
3. Remove special sections: references, citations, footnotes (optional)

## Next Steps

1. **Generate list:**
   ```bash
   python -m eu_fact_force.ingestion.data_collection.free_ground_truth \
       --output-csv ground_truth_50_articles.csv
   ```

2. **Download articles:**
   ```bash
   python -m eu_fact_force.ingestion.data_collection.download_ground_truth \
       --csv ground_truth_50_articles.csv \
       --output-dir ./ground_truth_data
   ```

3. **Verify downloads:**
   ```bash
   ls ground_truth_data/pdf/ | wc -l    # Should be ~50
   ls ground_truth_data/text/ | wc -l   # Should be ~50
   ```

4. **Evaluate your parser:**
   ```python
   # Your custom evaluation script
   from eu_fact_force.exploration.parsing_benchmarking.quality_scoring import *
   # ...
   ```

## Files

- **`free_ground_truth.py`** — Search for articles (25 vaccine + 25 other)
- **`download_ground_truth.py`** — Download PDFs + extract text versions
- **`GROUND_TRUTH_COLLECTION.md`** — This guide

All use **100% free APIs** (no authentication required beyond email for PubMed).
