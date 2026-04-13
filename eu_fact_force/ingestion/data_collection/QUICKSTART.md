# Seed Database Collection - Quick Start

Build a 33-50 article seed database for vaccines-autism evaluation in **5 minutes**.

## One-Command Full Pipeline

```bash
python -m eu_fact_force.ingestion.data_collection.seed_db full \
    --query "vaccine autism" \
    --output-dir ./vaccine_autism_seed \
    --max-articles 50
```

This will:
1. ✅ Search PubMed + Crossref for 100+ relevant articles
2. ✅ Deduplicate and rank by open access status
3. ✅ Ingest top 50 articles (fetch metadata + PDFs)
4. ✅ Save results to `./vaccine_autism_seed/`

## Output Directories

After the command completes:

```
vaccine_autism_seed/
├── search_results.json         # All 100+ search results (metadata only)
├── json/                       # Metadata JSON for 50 ingested articles
├── pdf/                        # PDFs for articles (where available)
├── ingestion_manifest.json     # Success/failure status per article
└── seed_db_report.json         # Summary stats
```

## Next Steps: Set Up Evaluation Ground Truth

### For Parsing Evaluation

```bash
# Copy articles to ground truth directory
cp vaccine_autism_seed/json/* \
    eu_fact_force/exploration/parsing_benchmarking/ground_truth/articles/

# Now you can benchmark parsing on real vaccine-autism papers:
python -m eu_fact_force.exploration.parsing_benchmarking.quality_scoring \
    --doc-type vaccine_autism \
    --configs docling_markdown
```

### For Search/Embedding Evaluation

```bash
# Create search queries and relevance judgments
mkdir -p vaccine_autism_evaluation/

# List ingested articles
ls vaccine_autism_seed/json/ | sed 's/.json$//' > \
    vaccine_autism_evaluation/article_ids.txt

# Create search_queries.json (see example below)
cat > vaccine_autism_evaluation/search_queries.json << 'EOF'
[
  {"id": "q1", "text": "does MMR vaccine cause autism"},
  {"id": "q2", "text": "vaccine autism study Wakefield debunked"},
  {"id": "q3", "text": "evidence vaccines safe children development"},
  {"id": "q4", "text": "autism spectrum disorder vaccination link"},
  {"id": "q5", "text": "thimerosal mercury vaccine safety"}
]
EOF

# Create relevance_judgments.json (manually annotate which articles are relevant)
# Format: {"q1": ["10_xxxx_yyyy", "10_yyyy_zzzz"], "q2": [...], ...}
```

## Customizing the Search

### Different Query Topics

```bash
# COVID vaccines
--query "COVID vaccination efficacy safety clinical trial"

# Moderate alcohol
--query "moderate alcohol cardiovascular health benefits"

# Any health topic
--query "TOPIC refutation debunk safety evidence"
```

### Filter by Year

```bash
# Only recent articles (2015+)
--query "vaccine autism" --min-year 2015
```

### Metadata Only (Faster)

```bash
# Skip PDF downloads for faster ingestion
--skip-pdf
```

## Checking Results

### Search Results Stats

```bash
python -c "
import json
with open('vaccine_autism_seed/search_results.json') as f:
    data = json.load(f)
    s = data['summary']
    print(f\"Total: {s['total_unique']}\")
    print(f\"Open access: {s['open_access_count']}\")
    print(f\"PubMed: {s['pubmed_count']}\")
    print(f\"Crossref: {s['crossref_count']}\")
"
```

### Ingestion Success Rate

```bash
python -c "
import json
with open('vaccine_autism_seed/seed_db_report.json') as f:
    r = json.load(f)
    print(f\"Ingested: {r['articles_ingested']}/{r['articles_requested']}\")
    print(f\"Success rate: {r['success_rate']}%\")
"
```

### Inspect a Single Article's Metadata

```bash
# List first article's metadata
cat vaccine_autism_seed/json/$(ls vaccine_autism_seed/json/ | head -1)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **No PDFs downloaded** | Some articles are metadata-only. Use `--skip-pdf` for faster ingestion. |
| **Command hangs** | API timeouts are normal. Ctrl+C and resume from where it stopped. |
| **Many ingestion failures** | Check network connectivity. Some DOIs may not have metadata in APIs. |
| **Rate limit errors** | Wait 5 minutes and try again. APIs are generally permissive. |

## Advanced: Resume an Interrupted Ingestion

If the process interrupts mid-way, check how many succeeded:

```bash
ls vaccine_autism_seed/json/ | wc -l
```

Then resume from that point using `batch_ingest.py` directly:

```bash
python -m eu_fact_force.ingestion.data_collection.batch_ingest \
    --search-results vaccine_autism_seed/search_results.json \
    --output-dir vaccine_autism_seed \
    --start-at 25 \
    --max-articles 50
```

## What's in Each Metadata JSON?

Example structure (from `json/10_xxxx_yyyy.json`):

```json
{
  "id": "10_xxxx_yyyy",
  "found": true,
  "sources": ["crossref", "pubmed"],
  "article name": "Vaccines and Autism: A Critical Review of the Evidence",
  "authors": ["Smith, John", "Doe, Jane"],
  "doi": "10.xxxx/yyyy",
  "journal": "Journal of Public Health",
  "publish date": "2020-06-15",
  "status": "published",
  "open access": true,
  "document type": "journal-article"
}
```

This is ready to be parsed by your pipeline and evaluated for parsing quality.
