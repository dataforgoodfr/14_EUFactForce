import requests

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------

API_ORDER = ["CrossRef", "HAL", "OpenAlex", "PubMed"]

API_CONFIG = {
    "HAL": {
        "url": "https://api.archives-ouvertes.fr/search/?q=doiId_s:",
        "url_suffix": "&fl=*",
        "response_root": "/response/docs/0",
        "fields": {
            "article name":  "title_s",
            "author":        "authFullName_s",
            "journal":       "journalTitle_s",
            "publish date":  "publicationDate_s",
            "link":          "uri_s",
            "keywords":      {"fallback": ["mesh_s", "keyword_s"]},
            "cited articles": "",
            "doi code":      "doiId_s",
            "article type":  "docType_s",
            "open access":   "openAccess_bool",
            "status":        "",
        },
    },
    "CrossRef": {
        "url": "https://api.crossref.org/works/doi/",
        "response_root": "",
        "fields": {
            "article name": "/message/title/0",
            "author": {
                "path": "/message/author",
                "each": {
                    "format": "{first} {last}",
                    "fields": {
                        "first": {"path": "given"},
                        "last":  {"path": "family"},
                    },
                },
            },
            "journal":       "message/publisher",
            "publish date":  {"path": "/message/published/date-parts/0", "join": "-", "pad": 2},
            "link":          "message/resource/primary/URL",
            "keywords":      "",
            "cited articles": {
                "path": "/message/reference",
                "each": {"extract_first": ["DOI", "unstructured"]},
            },
            "doi code":     "/message/DOI",
            "article type": "/message/type",
            "open access":  "",
            "status": {
                "path": "/message/updated-by",
                "default": "published",
                "each": {
                    "format": "{type} on {date}",
                    "fields": {
                        "type": {"path": "type", "labels": {"correction": "corrected", "retraction": "retracted"}},
                        "date": {"path": "updated/date-time", "slice": 10},
                    },
                },
            },
        },
    },
    "OpenAlex": {
        "url": "https://api.openalex.org/works/doi:",
        "response_root": "",
        "fields": {
            "article name":  "title",
            "author":        {"path": "authorships", "each": {"extract": "raw_author_name"}},
            "journal":       "primary_location/source/host_organization_name",
            "publish date":  "publication_date",
            "link":          "best_oa_location/pdf_url",
            "keywords":      {"path": "mesh", "each": {"extract": "descriptor_name", "unique": True}},
            "cited articles": {
                "path": "referenced_works",
                "fetch": {
                    "url": "https://api.openalex.org/works?filter=ids.openalex:{ids}&select=id,{field}&per-page=200",
                    "id_from": "url_last_segment",
                    "field": "doi",
                },
            },
            "doi code":     {"path": "doi", "strip_prefix": "https://doi.org/"},
            "article type": "type",
            "open access":  "open_access/is_oa",
            "status":       {"path": "is_retracted", "if_true": "retracted", "if_false": "published"},
        },
    },
    "PubMed": {
        "resolve": {
            "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            "params": {"db": "pubmed", "retmode": "json"},
            "doi_term": "[DOI]",
            "id_path": "/esearchresult/idlist/0",
        },
        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=",
        "url_suffix": "&retmode=json",
        "response_root": "/result/{id}",
        "fields": {
            "article name":  "title",
            "author":        {"path": "authors", "each": {"extract": "name"}},
            "journal":       "fulljournalname",
            "publish date":  "pubdate",
            "link":          "",
            "keywords":      "",
            "cited articles": "",
            "doi code":      {"path": "articleids", "each": {"filter": {"idtype": "doi"}, "extract": "value"}},
            "article type":  "pubtype/0",
            "open access":   "",
            "status":        {"path": "pubtype", "any_contains": "Retracted Publication", "if_true": "retracted", "if_false": "published"},
        },
    },
}

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------

def _resolve_path(data, path: str):
    """Navigate a slash-separated path through nested dicts and lists. Returns None if any segment is missing."""
    for part in path.strip("/").split("/"):
        if data is None:
            return None
        try:
            data = data[int(part)] if isinstance(data, list) else data.get(part)
        except (IndexError, ValueError, TypeError):
            return None
    return data


def _extract_each(items: list, spec: dict):
    """Apply an extraction spec to each item in a list and return the collected results."""
    if "filter" in spec:
        items = [item for item in items if all(item.get(k) == v for k, v in spec["filter"].items())]
    results = []
    for item in items:
        if "extract" in spec:
            val = _resolve_path(item, spec["extract"])
            if val is not None:
                results.append(val)
        elif "extract_first" in spec:
            for field in spec["extract_first"]:
                if field in item:
                    results.append(item[field])
                    break
        elif "format" in spec:
            fields = {}
            for name, field_spec in spec["fields"].items():
                val = _resolve_path(item, field_spec["path"])
                if "slice" in field_spec:
                    val = str(val or "")[:field_spec["slice"]]
                if "labels" in field_spec:
                    val = field_spec["labels"].get(val, val)
                fields[name] = val
            results.append(spec["format"].format(**fields))
    if spec.get("unique"):
        results = list(dict.fromkeys(results))
    return results[0] if len(results) == 1 else results


def _fetch_secondary(urls: list, spec: dict) -> list:
    """Fetch a single field for a batch of resource URLs via a secondary API call."""
    if not urls:
        return []
    field = spec["field"]
    ids = [u.split("/")[-1] for u in urls] if spec.get("id_from") == "url_last_segment" else urls
    url = spec["url"].format(ids="|".join(ids), field=field)
    response = requests.get(url)
    response.raise_for_status()
    return [r[field] for r in response.json().get("results", []) if r.get(field)]


def _extract_field(data: dict, doc: dict, path):
    """Resolve a metadata field from an API response according to a path spec.

    Supported path specs:
    - ""                                         → None
    - "key" or "nested/path"                     → resolve from doc
    - "/absolute/path"                           → resolve from response root
    - {"fallback": [p1, p2]}                     → first non-null among listed paths
    - {"path": ..., "default": v}                → value at path, or default if null
    - {"path": ..., "if_true": x, "if_false": y} → boolean mapped to string
    - {"path": ..., "strip_prefix": s}           → remove prefix from string value
    - {"path": ..., "join": sep, "pad": n}       → join list as string
    - {"path": ..., "each": spec}                → apply spec to each list item
    - {"path": ..., "fetch": spec}               → secondary HTTP batch fetch
    """
    if isinstance(path, dict):
        if "fallback" in path:
            for p in path["fallback"]:
                value = _extract_field(data, doc, p)
                if value:
                    return value
            return None
        if "path" in path:
            value = _extract_field(data, doc, path["path"])
            if "any_contains" in path:
                return path["if_true"] if path["any_contains"] in (value or []) else path["if_false"]
            if "if_true" in path:
                return path["if_true"] if value else path["if_false"]
            if not value:
                return path.get("default")
            if "strip_prefix" in path:
                return str(value).removeprefix(path["strip_prefix"])
            if "join" in path:
                return path["join"].join(str(p).zfill(path.get("pad", 0)) for p in value)
            if "fetch" in path:
                return _fetch_secondary(value, path["fetch"])
            if "each" in path:
                result = _extract_each(value, path["each"])
                return result if result else path.get("default")
            return value
        return {k: _extract_field(data, doc, v) for k, v in path.items()}
    if not path:
        return None
    if path.startswith("/"):
        return _resolve_path(data, path)
    return _resolve_path(doc, path)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_metadata(doi: str, api: str) -> dict:
    """Fetch metadata for a DOI from a single API. Returns a dict with "found" as first key."""
    config = API_CONFIG.get(api)
    if config is None:
        raise ValueError(f"Unknown API: {api}. Choose from {list(API_CONFIG)}")

    resolved_id = doi
    if "resolve" in config:
        resolve_cfg = config["resolve"]
        params = dict(resolve_cfg.get("params", {}))
        params["term"] = doi + resolve_cfg.get("doi_term", "")
        r = requests.get(resolve_cfg["url"], params=params)
        r.raise_for_status()
        resolved_id = _resolve_path(r.json(), resolve_cfg["id_path"])
        if not resolved_id:
            print(f"DOI not found in {api}: {doi}")
            return {"found": False}

    url = config["url"] + resolved_id + config.get("url_suffix", "")
    response = requests.get(url)
    if response.status_code == 404:
        print(f"DOI not found in {api}: {doi}")
        return {"found": False}
    response.raise_for_status()
    data = response.json()

    response_root = config.get("response_root", "").replace("{id}", resolved_id)
    doc = _resolve_path(data, response_root) if response_root else data
    if doc is None:
        print(f"DOI not found in {api}: {doi}")
        return {"found": False}

    return {"found": True} | {
        field_name: _extract_field(data, doc, path)
        for field_name, path in config["fields"].items()
    }


def _is_more_complete(new, current) -> bool:
    """Return True if new value is more complete than current (longer list or longer string)."""
    if isinstance(new, list) and isinstance(current, list):
        return len(new) > len(current)
    if isinstance(new, str) and isinstance(current, str):
        return len(new) > len(current)
    return False


def fetch_metadata_all_apis(doi: str) -> dict:
    """Fetch and merge metadata for a DOI across all APIs in API_ORDER.

    For each field, keeps the most complete value found (longest list or string).
    Returns a dict with "found" and "sources" as first keys, followed by all metadata fields.
    """
    all_fields = dict.fromkeys(f for api in API_ORDER for f in API_CONFIG[api]["fields"])
    merged = {field: None for field in all_fields}
    sources = []

    for api in API_ORDER:
        result = fetch_metadata(doi, api)
        if not result.get("found"):
            continue
        sources.append(api)
        for field, value in result.items():
            if field == "found" or value is None:
                continue
            if merged.get(field) is None or _is_more_complete(value, merged[field]):
                merged[field] = value

    return {"found": bool(sources), "sources": sources} | merged


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Fetch metadata for a DOI.")
    parser.add_argument("--doi", default="10.1016/S0140-6736(97)11096-0")
    parser.add_argument("--api", default=None, choices=list(API_CONFIG) + [None])
    args = parser.parse_args()

    result = fetch_metadata_all_apis(args.doi) if args.api is None else fetch_metadata(args.doi, args.api)
    print(json.dumps(result, indent=2, ensure_ascii=False))
