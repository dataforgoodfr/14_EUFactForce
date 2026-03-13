import json
import sys

import requests
import argparse

OPENALEX_API_KEY = "AtCqIiBpdcCzao86YBx2L2"

api_to_metadata = {
    "HAL": {
        "url": "https://api.archives-ouvertes.fr/search/?q=doiId_s:",
        "url_suffix": "&fl=*",
        "response_root": "/response/docs/0",  # path to the document in the response
        "metadata_fields": {
            "author": "authFullName_s",
            "journal": "journalTitle_s",
            "link": "uri_s",
            "keywords": "mesh_s",
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
        "response_root": "",  # fields use absolute paths from root
        "metadata_fields": {
            "author": {
                "first_name": "/message/author/0/given",
                "last_name": "/message/author/0/family"
            },
            "journal": "message/publisher",
            "link": "message/resource/primary/URL",
            "keywords": "",
            "publish date": {
                "year": "/message/published/date-parts/0/0",
                "month": "/message/published/date-parts/0/1",
                "day": "/message/published/date-parts/0/2",
            },
            "cited articles": {"key": "message", "extract": "reference"},  # id/DOI ou unstructured
            "article name": "/message/title/0",
            "doi code": "/message/DOI",
            "article type": "/message/type",
            "open_access": "",
            "status": {
                "updated" : "/message/updated_by", # id/type (can be "correction", "retraction")
            }
        }
    },
    "OpenAlex": {
        "url": "https://api.openalex.org/works/doi:",  # ?api_key={OPENALEX_API_KEY}
        "response_root": "",
        "metadata_fields": {
            "author": {"key": "authorships", "extract": "raw_author_name"},
            "journal": "locations/0/source/host_organization_name",
            "link" : "best_oa_location/pdf_url",
            "keywords": {"key": "mesh", "extract": "descriptor_name"},
            "publish date": "publication_date",
            "cited articles": "referenced_works",  # id (donne un lien openalex auquel on ajoute api. avant openalex pour avoir les métadonnées)
            "article name": "title",
            "doi code": "doi",
            "article type": "type",
            "open access": "open_access/is_oa", #boolean
            "status": {
                "accepted": "locations/0/is_accepted",
                "published": "locations/0/is_published",
                "retracted": "is_retracted"
            }
        }
    }
}


def resolve_path(data: dict, path: str):
    """Navigate a slash-separated JSON path like /message/author/0/given."""
    for part in path.strip("/").split("/"):
        if data is None:
            return None
        data = data[int(part)] if isinstance(data, list) else data.get(part)
    return data


def _extract_field(data: dict, doc: dict, path):
    """
    Resolve a field value:
    - {"key": ..., "extract": ...} → get a list, return unique values of the given subkey
    - {"k": "v", ...} without "key"  → resolve each value recursively (e.g. author sub-fields)
    - "/absolute/path"               → resolve from response root
    - "plain_key"                    → simple lookup on extracted doc
    """
    if isinstance(path, dict):
        if "key" in path and "extract" in path:
            items = doc.get(path["key"]) or []
            return list(dict.fromkeys(item[path["extract"]] for item in items if path["extract"] in item))
        return {k: _extract_field(data, doc, v) for k, v in path.items()}
    if not path:
        return None
    if path.startswith("/"):
        return resolve_path(data, path)
    return doc.get(path)


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
    parser.add_argument("--doi", required=False, default="10.1038/nature12373", help="DOI of the article")
    parser.add_argument("--api", required=False, default="CrossRef", choices=api_to_metadata.keys(), help="API to use (HAL, CrossRef, OpenAlex)")
    args = parser.parse_args()

    doi = args.doi
    api = args.api
    metadata = fetch_metadata(doi, api)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
