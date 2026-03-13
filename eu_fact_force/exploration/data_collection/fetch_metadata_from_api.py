import json

import requests
import argparse

OPENALEX_API_KEY = "AtCqIiBpdcCzao86YBx2L2"

api_to_metadata = {
    "HAL": {
        "url": "https://api.archives-ouvertes.fr/search/?q=doiId_s:",
        "url_suffix": "&fl=*",
        "response_root": "/response/docs/0",
        "metadata_fields": {
            "author": "authFullName_s",
            "journal": "journalTitle_s",
            "link": "uri_s",
            "keywords": {"fallback": ["mesh_s", "keyword_s"]},
            "publish date": "publicationDate_s",
            "cited articles": "",
            "article name": "title_s",
            "doi code": "doiId_s",
            "article type": "docType_s",
            "open access": "openAccess_bool",
            "status": "",
        }
    },
    "CrossRef": {
        "url": "https://api.crossref.org/works/doi/",
        "response_root": "",
        "metadata_fields": {
            "author": {
                "path": "/message/author",
                "each": {
                    "format": "{first} {last}",
                    "fields": {
                        "first": {"path": "given"},
                        "last": {"path": "family"}
                    }
                }
            },
            "journal": "message/publisher",
            "link": "message/resource/primary/URL",
            "keywords": "",
            "publish date": {"path": "/message/published/date-parts/0", "join": "-", "pad": 2},
            "cited articles": {
                "path": "/message/reference",
                "each": {"extract_first": ["DOI", "unstructured"]}
            },
            "article name": "/message/title/0",
            "doi code": "/message/DOI",
            "article type": "/message/type",
            "open_access": "",
            "status": {
                "path": "/message/updated-by",
                "default": "published",
                "each": {
                    "format": "{type} on {date}",
                    "fields": {
                        "type": {"path": "type", "labels": {"correction": "corrected", "retraction": "retracted"}},
                        "date": {"path": "updated/date-time", "slice": 10}
                    }
                }
            }
        }
    },
    "OpenAlex": {
        "url": "https://api.openalex.org/works/doi:",
        "response_root": "",
        "metadata_fields": {
            "author": {"path": "authorships", "each": {"extract": "raw_author_name"}},
            "journal": "primary_location/source/host_organization_name",
            "link": "best_oa_location/pdf_url",
            "keywords": {"path": "mesh", "each": {"extract": "descriptor_name", "unique": True}},
            "publish date": "publication_date",
            "cited articles": {
                "path": "referenced_works",
                "fetch": {
                    "url": "https://api.openalex.org/works?filter=ids.openalex:{ids}&select=id,{field}&per-page=200",
                    "id_from": "url_last_segment",
                    "field": "doi"
                }
            },
            "article name": "title",
            "doi code": "doi",
            "article type": "type",
            "open access": "open_access/is_oa",
            "status": {"path": "is_retracted", "if_true": "retracted", "if_false": "published"}
        }
    }
}


def resolve_path(data, path: str):
    """Navigate a slash-separated path: /a/b/0/c, a/b/c, or plain_key."""
    for part in path.strip("/").split("/"):
        if data is None:
            return None
        data = data[int(part)] if isinstance(data, list) else data.get(part)
    return data


def _extract_each(items: list, spec: dict):
    """Apply a spec to each item in a list and return the collected results."""
    results = []
    for item in items:
        if "extract" in spec:
            val = resolve_path(item, spec["extract"])
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
                val = resolve_path(item, field_spec["path"])
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
    """Fetch a field for a list of resource URLs via a secondary batch API call."""
    if not urls:
        return []
    field = spec["field"]
    ids = [u.split("/")[-1] for u in urls] if spec.get("id_from") == "url_last_segment" else urls
    url = spec["url"].format(ids="|".join(ids), field=field)
    response = requests.get(url)
    response.raise_for_status()
    return [r[field] for r in response.json().get("results", []) if r.get(field)]


def _extract_field(data: dict, doc: dict, path):
    """Resolve a field from the API response according to a path spec.

    Supported specs:
    - ""                          → None
    - "plain_key"                 → doc["plain_key"]
    - "nested/path"               → resolve from doc
    - "/absolute/path"            → resolve from response root
    - {"fallback": [...]}         → first non-null among listed paths
    - {"path": ..., "default": ...}              → path or default if null
    - {"path": ..., "if_true": x, "if_false": y} → boolean to string
    - {"path": ..., "join": "-", "pad": 2}        → join list elements as string
    - {"path": ..., "each": {spec}}               → iterate list, apply spec per item
    - {"path": ..., "fetch": {spec}}              → secondary HTTP batch fetch
    - {k: v, ...}                                 → nested dict, resolve each value
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
            if "if_true" in path:
                return path["if_true"] if value else path["if_false"]
            if not value:
                return path.get("default")
            if "join" in path:
                pad = path.get("pad", 0)
                return path["join"].join(str(p).zfill(pad) for p in value)
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
        return resolve_path(data, path)
    return resolve_path(doc, path)


def fetch_metadata(doi: str, api: str) -> dict:
    config = api_to_metadata.get(api)
    if config is None:
        raise ValueError(f"Unknown API: {api}. Choose from {list(api_to_metadata)}")

    url = config["url"] + doi + config.get("url_suffix", "")
    print(url)
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    response_root = config.get("response_root", "")
    doc = resolve_path(data, response_root) if response_root else data

    return {
        field_name: _extract_field(data, doc, path)
        for field_name, path in config["metadata_fields"].items()
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch metadata for a DOI from a specified API.")
    parser.add_argument("--doi", required=False, default="10.1016/S0140-6736(97)11096-0", help="DOI of the article")
    parser.add_argument("--api", required=False, default="CrossRef", choices=api_to_metadata.keys(), help="API to use (HAL, CrossRef, OpenAlex)")
    args = parser.parse_args()

    metadata = fetch_metadata(args.doi, args.api)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
