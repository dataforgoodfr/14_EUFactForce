# Seed Database Collection

Build a seed database of scientific articles on a health topic (e.g., vaccines-autism) for evaluating parsing and embedding quality.

## Quick Start

```bash
# Full pipeline: search + ingest 50 articles on vaccines-autism
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism refutation safety" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50

# Then expand to ground truth for evaluation
cp -r vaccine_autism_seed/json eu_fact_force/exploration/parsing_benchmarking/ground_truth/
```

## Workflow

### 1. Search (PubMed + Crossref)

```bash
python -m eu_fact_force.ingestion.data_collection.seed_db search \
    --query "vaccine autism" \
    --output-dir ./vax_autism_seed \
    --max-results 100 \
    --min-year 2010
```

**Output:**
- `vax_autism_seed/search_results.json` — List of 100+ articles with:
  - DOI, title, authors
  - Journal, publication date
  - Open access status
  - Source (PubMed or Crossref)

### 2. Ingest (Fetch metadata + PDFs)

```bash
python -m eu_fact_force.ingestion.data_collection.seed_db ingest \
    --search-results ./vax_autism_seed/search_results.json \
    --output-dir ./vax_autism_seed \
    --max-articles 50
```

**Output:**
- `vax_autism_seed/json/` — Metadata JSON files (one per article)
- `vax_autism_seed/pdf/` — Full-text PDFs (where available)
- `vax_autism_seed/ingestion_manifest.json` — Status report

### 3. Full Pipeline (Search + Ingest)

```bash
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50 \
    --skip-pdf  # Optional: metadata only, faster
```

## Search Query Tips

### For Vaccine-Autism Narrative

Good queries (refined to exclude hoax promoters):
```
"vaccine autism" AND (refuted OR debunk OR disproven OR safety OR efficacy)
"vaccine" AND "autism" AND ("safety" OR "effectiveness" OR "no link")
```

Directly in search (PubMed supports these operators):
```bash
# Include refutations, exclude Wakefield
--query '("vaccine" OR "vaccination") AND ("autism" OR "autistic") AND ("refut*" OR "debunk*" OR "disproven")'
```

### For Other Narratives

- **Moderate alcohol**: `"moderate alcohol" AND ("cardiovascular" OR "health")`
- **COVID misinformation**: `"COVID" AND ("vaccines" OR "efficacy") AND ("study" OR "clinical")`

## Output Structure

```
vaccine_autism_seed/
├── search_results.json          # All search results (100+ articles)
├── seed_db_report.json          # Final ingestion report
├── json/                        # Metadata for ingested articles
│   ├── 10_xxxx_yyyy.json
│   ├── 10_xxxx_zzzz.json
│   └── ... (up to 50 articles)
├── pdf/                         # Full-text PDFs (where available)
│   ├── 10_xxxx_yyyy_pubmed.pdf
│   ├── 10_xxxx_yyyy_crossref.pdf
│   └── ...
└── ingestion_manifest.json      # Detailed ingestion status
```

## Filtering & Quality Control

### Open Access Preference

The search automatically prioritizes open access articles. To see counts:

```bash
python -c "
import json
with open('vaccine_autism_seed/search_results.json') as f:
    data = json.load(f)
    oa = sum(1 for r in data['results'] if r.get('open_access'))
    print(f'Open access: {oa}/{len(data[\"results\"])} ({oa*100//len(data[\"results\"])}%)')
"
```

### Publication Date Filtering

Use `--min-year` to focus on recent literature:

```bash
--min-year 2015  # Articles from 2015 onwards
```

### Manual Curation

After ingestion, inspect `json/` and remove articles that are:
- Duplicates
- Unrelated to the narrative
- Retracted publications (check metadata `"status"` field)

## Integration with Evaluation

### For Parsing Benchmarking

To add your seed database to parsing evaluation:

```bash
# Copy ingested metadata to ground truth
cp vaccine_autism_seed/json/* \
    eu_fact_force/exploration/parsing_benchmarking/ground_truth/articles/

# Add to ground_truth.json (see parsing_benchmarking README)
```

### For Search Quality Evaluation

Create evaluation ground truth:

```bash
# After ingesting articles
mkdir -p eu_fact_force/exploration/search_benchmarking/vaccine_autism/

# List article IDs (for relevance judgments)
ls vaccine_autism_seed/json/*.json | xargs -I {} basename {} .json | sort > \
    eu_fact_force/exploration/search_benchmarking/vaccine_autism/article_ids.txt

# Manually create search_queries.json with evaluation queries
# (see prd-canonical-document.md for example structure)
```

## Troubleshooting

### No PDFs Downloaded

Some articles are metadata-only (no open PDF available). This is normal. Use `--skip-pdf` for faster ingestion:

```bash
python -m eu_fact_force.ingestion.data_collection.seed_db ingest \
    --search-results search_results.json \
    --output-dir ./output \
    --max-articles 50 \
    --skip-pdf
```

### API Rate Limits

PubMed and Crossref are generally permissive, but if you hit rate limits:
- Wait a few minutes
- Resume with `--start-at <index>` (batch_ingest.py only)

### Missing Metadata Fields

Different sources (PubMed, Crossref, OpenAlex) return different metadata. The `collector.fetch_all()` merges them intelligently:
- Prefers longer/fuller values
- Keeps both values in source-specific fields

Check the JSON output to see which fields came from which source.

## Example: Build a 50-article Vaccine-Autism Database

```bash
#!/bin/bash

# 1. Search
python -m eu_fact_force.ingestion.data_collection.seed_db search \
    --query '("vaccine" OR "vaccination") AND ("autism" OR "autistic") AND ("refut*" OR "debunk*" OR "safe")' \
    --output-dir ./vaccine_autism \
    --max-results 100 \
    --min-year 2010

# 2. Check search results
cat vaccine_autism/search_results.json | jq '.summary'

# 3. Ingest top 50
python -m eu_fact_force.ingestion.data_collection.seed_db ingest \
    --search-results ./vaccine_autism/search_results.json \
    --output-dir ./vaccine_autism \
    --max-articles 50

# 4. Check results
ls vaccine_autism/json/ | wc -l  # Should be ~50
cat vaccine_autism/seed_db_report.json | jq '.success_rate'
```

## API Authentication & Terms

### PubMed (NCBI)

- **Authentication**: None required, but you must provide an email (bot@dataforgood.fr is used)
- **Terms**: Free academic use; do not overload with rapid requests
- **Rate limit**: ~3 requests/second recommended

### Crossref

- **Authentication**: None required
- **Terms**: Free, no login needed; polite requests encouraged
- **User-Agent**: Required (included in code)

## References

- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/)
- [Crossref API](https://github.com/CrossRef/rest-api-doc)
- [OpenAlex API](https://docs.openalex.org/)
