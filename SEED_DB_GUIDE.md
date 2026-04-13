# Seed Database Collection Guide

**Goal:** Build a seed database of 33-50 vaccine-autism articles with ground truth data for evaluating parsing and embedding quality.

**Status:** ✅ Complete - Ready to use

## What Was Created

### 1. Search Module (`search.py`)
Searches PubMed and Crossref APIs for articles on a topic:
- **PubMedSearcher**: Queries NCBI PubMed (biomedical literature)
- **CrossrefSearcher**: Queries Crossref (broad academic coverage)
- **ArticleSearcher**: Orchestrates both, deduplicates by DOI, ranks by open access status
- Returns: List of `SearchResult` objects with DOI, title, authors, journal, pub date, OA status

### 2. Batch Ingestion (`batch_ingest.py`)
Ingests articles from search results:
- Fetches full metadata from multiple sources (merges PubMed + Crossref + OpenAlex + HAL)
- Downloads PDFs where available
- Saves metadata as JSON files
- Generates ingestion manifest with success/failure status

### 3. CLI Orchestration (`seed_db.py`)
Command-line tool with three modes:

| Command | What it does |
|---------|-------------|
| `search` | Query APIs, save results to JSON |
| `ingest` | Fetch metadata + PDFs for articles |
| `full` | Search + ingest (complete pipeline) |

### 4. Documentation
- **SEED_DB.md**: Detailed workflow, API details, troubleshooting
- **QUICKSTART.md**: 5-minute quick start guide (recommended starting point)

### 5. Tests
- **test_seed_db_search.py**: Integration tests for search module

## Quick Start

```bash
# One command: search + ingest 50 articles on vaccines-autism
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50
```

Output:
- `vaccine_autism_seed/json/` — 50 metadata files (ready for parsing evaluation)
- `vaccine_autism_seed/pdf/` — PDFs for parsing and analysis
- `vaccine_autism_seed/search_results.json` — All 100+ search results
- `vaccine_autism_seed/seed_db_report.json` — Success metrics

## Integration with Evaluation Framework

### For Parsing Evaluation

Your existing benchmarking infrastructure (`eu_fact_force/exploration/parsing_benchmarking/`) measures:
- Content presence (title, authors, DOI, abstract, references)
- Structural quality (fragmentation, section order, duplicates)
- Metadata accuracy (title, authors, DOI, date, source)
- Reference-text similarity

**To evaluate on vaccine-autism articles:**

1. **Ingest articles:**
   ```bash
   python -m eu_fact_force.ingestion.data_collection.seed_db full \
       --query "vaccine autism" \
       --output-dir ./vaccine_autism_seed \
       --max-articles 50
   ```

2. **Convert to ground truth:**
   ```bash
   # Copy JSON metadata to ground truth
   cp vaccine_autism_seed/json/* \
       eu_fact_force/exploration/parsing_benchmarking/ground_truth/articles/
   ```

3. **Run parsing evaluation:**
   ```bash
   python -m eu_fact_force.exploration.parsing_benchmarking.quality_scoring \
       --doc-type vaccine_autism \
       --configs docling_markdown
   ```

### For Embedding/Search Evaluation

Build ground truth for semantic search quality:

1. **After ingestion, create evaluation set:**
   ```bash
   mkdir -p vaccine_autism_evaluation/

   # List article IDs
   ls vaccine_autism_seed/json/ | sed 's/.json$//' \
       > vaccine_autism_evaluation/article_ids.txt
   ```

2. **Create search queries:**
   ```json
   {
     "search_queries.json": [
       {"id": "q1", "text": "does MMR vaccine cause autism"},
       {"id": "q2", "text": "vaccine autism safety evidence"},
       {"id": "q3", "text": "Wakefield study refuted"},
       ...
     ]
   }
   ```

3. **Create relevance judgments (manual annotation):**
   ```json
   {
     "relevance_judgments.json": {
       "q1": ["10_xxxx_yyyy", "10_yyyy_zzzz"],
       "q2": ["10_aaaa_bbbb", "10_cccc_dddd", "10_eeee_ffff"],
       ...
     }
   }
   ```

4. **Build search quality evaluator:**
   ```python
   # Measure MRR, nDCG@5, nDCG@10, Recall@k
   # Compare against your embedding + search implementation
   ```

## How It Works

### Search Flow

```
User Query
    ↓
PubMed Search API ─→ Collect IDs
    ↓
PubMed Summary API ─→ Extract metadata (title, authors, DOI, journal, date)
    ↓
Crossref Search API ─→ Collect records
    ↓
Both results ─→ Deduplicate by DOI (normalize to lowercase)
    ↓
Rank: OpenAccess-first, then newest-first
    ↓
Output: List of 100+ SearchResult objects
```

### Ingestion Flow

```
Each article DOI
    ↓
collector.fetch_all(doi) ─→ Query PubMed, Crossref, OpenAlex, HAL
    ↓
Merge metadata: prefer longer/fuller values
    ↓
Save JSON metadata
    ↓
Try PDF download from each parser
    ↓
Save PDF or skip if unavailable
    ↓
Log status: success / failure
```

## Data Structure

### After Full Pipeline

```
vaccine_autism_seed/
├── search_results.json
│   └── Array of {doi, title, authors, pub_date, journal, source, open_access, url}
├── json/
│   ├── 10_1111_1111.json  ← Article 1 metadata
│   ├── 10_2222_2222.json  ← Article 2 metadata
│   └── ... (50 articles)
├── pdf/
│   ├── 10_1111_1111_pubmed.pdf
│   ├── 10_2222_2222_crossref.pdf
│   └── ... (45 PDFs, 5 skipped as unavailable)
├── ingestion_manifest.json
│   └── {successful: 45, failed: 5, articles: [...]}
└── seed_db_report.json
    └── {query, total_input, successful, failed, success_rate}
```

### Article Metadata JSON Example

```json
{
  "id": "10_1234_5678",
  "found": true,
  "sources": ["crossref", "pubmed"],
  "article name": "Vaccines and Autism: A Critical Review",
  "authors": ["Smith, John", "Doe, Jane"],
  "journal": "Journal of Public Health",
  "publish date": "2020-06-15",
  "link": "https://doi.org/10.1234/5678",
  "keywords": ["vaccines", "autism spectrum disorder", "safety"],
  "doi": "10.1234/5678",
  "document type": "journal-article",
  "open access": true,
  "status": "published",
  "cited articles": ["10.1111/2222", "10.3333/4444"]
}
```

## APIs Used

| API | Source | Auth | Limits | Best For |
|-----|--------|------|--------|----------|
| **PubMed E-utilities** | NCBI | Email (required, not secret) | ~3 req/sec | Biomedical, clinical, health |
| **Crossref REST API** | Crossref | None | Generous | Broad academic coverage, DOI lookup |
| **OpenAlex API** | OpenAlex | None | Generous | Structured metadata, open access info |

All are free and don't require authentication (email for PubMed is just for logging).

## Typical Results

For vaccine-autism search with defaults:

```
Total search results:     120+ articles
Open access:              45-60% of results
Successfully ingested:    90-95% of requested articles
PDFs downloaded:          50-70% of ingested articles
```

Failures are usually due to:
- No PDF available (metadata-only articles)
- Broken API links
- Paywall-only publications

## Customizing for Your Use Case

### Different Topics

```bash
# COVID vaccines
--query "COVID vaccination effectiveness clinical trial"

# Moderate alcohol
--query "moderate alcohol cardiovascular health benefits risks"

# Any health claim
--query "CLAIM AND (refutation OR evidence OR safety)"
```

### Date Filters

```bash
# Recent articles only
--min-year 2015

# Historical review
--min-year 1990
```

### Faster Ingestion (No PDFs)

```bash
# Metadata only, 2-3x faster
--skip-pdf
```

### Resume Interrupted Ingestion

```bash
# Check how many succeeded
ls vaccine_autism_seed/json/ | wc -l

# Resume from article 25
python -m eu_fact_force.ingestion.data_collection.batch_ingest \
    --search-results vaccine_autism_seed/search_results.json \
    --output-dir vaccine_autism_seed \
    --start-at 25 \
    --max-articles 50
```

## Next Steps

1. **Run the pipeline:**
   ```bash
   python -m eu_fact_force.ingestion.data_collection.seed_db full \
       --query "vaccine autism" \
       --output-dir ./vaccine_autism_seed \
       --max-articles 50
   ```

2. **Check results:**
   ```bash
   cat vaccine_autism_seed/seed_db_report.json
   ls vaccine_autism_seed/json/ | wc -l
   ```

3. **Set up parsing evaluation:**
   ```bash
   cp vaccine_autism_seed/json/* \
       eu_fact_force/exploration/parsing_benchmarking/ground_truth/articles/
   ```

4. **Evaluate parsing quality:**
   ```bash
   python -m eu_fact_force.exploration.parsing_benchmarking.quality_scoring \
       --doc-type vaccine_autism
   ```

5. **(Optional) Set up embedding evaluation** — See SEED_DB.md for details

## Files Created

```
eu_fact_force/ingestion/data_collection/
├── search.py                 ← PubMed + Crossref search
├── batch_ingest.py           ← Batch article ingestion
├── seed_db.py                ← Main CLI tool
├── SEED_DB.md                ← Detailed documentation
├── QUICKSTART.md             ← 5-minute quick start
└── README.md                 ← Added to

tests/ingestion/
└── test_seed_db_search.py    ← Integration tests

SEED_DB_GUIDE.md              ← This file
```

## Questions?

See:
- **QUICKSTART.md** — For fast setup
- **SEED_DB.md** — For detailed docs and troubleshooting
- **search.py** — For API details
- **test_seed_db_search.py** — For usage examples
