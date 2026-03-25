# data_collection

Fetches metadata and PDFs for scientific articles by DOI, aggregating results across multiple APIs.

## Usage

Depuis la racine du projet :

```bash
python -m eu_fact_force.ingestion.data_collection --doi 10.1128/mbio.01735-25
```

| Flag | Default | Description |
|------|---------|-------------|
| `--doi` | *(required)* | DOI of the article |
| `--json-dir` | `json/` | Directory for metadata output |
| `--pdf-dir` | `pdf/` | Directory for PDF output |
| `--no-pdf` | | Skip PDF download |

**Output:** `<json-dir>/<id>.json` and optionally `<pdf-dir>/<id>_<api>.pdf`

The article `id` is the DOI with `/`, `-`, `.` replaced by `_`.

## Metadata fields

```json
{
  "id": "10_1128_mbio_01735-25",
  "found": true,
  "sources": ["CrossrefMetadataParser", "OpenAlexMetadataParser"],
  "article name": "...",
  "authors": ["Author One", "Author Two"],
  "journal": "...",
  "publish date": "2024-01-15",
  "link": "https://...",
  "keywords": ["keyword1", "keyword2"],
  "cited articles": ["10.1000/xyz123", "..."],
  "doi": "10.1128/mbio.01735-25",
  "document type": "journal-article",
  "open access": true,
  "status": "published"
}
```

Fields may be `null` if unavailable. For each field, the most complete value across all APIs is kept (longest list or string). `sources` lists which APIs returned a result.

## Parsers

| Parser | API | PDF |
|--------|-----|-----|
| `CrossrefMetadataParser` | [api.crossref.org](https://api.crossref.org) | Yes (if OA link available) |
| `OpenAlexMetadataParser` | [api.openalex.org](https://api.openalex.org) | Yes (OA locations) |
| `PubMedMetadataParser` | [eutils.ncbi.nlm.nih.gov](https://eutils.ncbi.nlm.nih.gov) | No |
| `HALMetadataParser` | [api.archives-ouvertes.fr](https://api.archives-ouvertes.fr) | Yes |
| `ArxivMetadataParser` | [arxiv.org](https://arxiv.org) | Yes (preprints only) |

## Adding a parser

1. Create `parsers/myapi.py` extending `MetadataParser`
2. Implement `get_metadata(doi) -> dict` and `get_pdf_url(doi) -> list[str]`
3. Add it to `PARSERS` in `parsers/__init__.py`

## Structure

```
data_collection/
  __init__.py      # package
  __main__.py      # CLI entry point
  collector.py     # fetch_all() — agrège les métadonnées de tous les parsers
  utils.py         # doi_to_id, dict_to_string
  parsers/
    __init__.py    # PARSERS list
    base.py        # MetadataParser base class + doi_to_id
    crossref.py
    openalex.py
    pubmed.py
    hal.py
    arxiv.py
```

Pour tester un parser seul, depuis la racine du projet :

```bash
python -m eu_fact_force.ingestion.data_collection.parsers.crossref
```
