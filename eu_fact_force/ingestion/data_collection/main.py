import argparse
import json
import os

from parsers import PARSERS
from utils import doi_to_id


def _better(new, current):
    """Return True if new is a longer list or string than current."""
    if isinstance(new, (list, str)) and isinstance(new, type(current)):
        return len(new) > len(current)
    return False


def fetch_all(doi: str) -> dict:
    """Query all parsers for a DOI and merge results, keeping the most complete value per field."""
    merged = {}
    sources = []
    for parser in PARSERS:
        print(f"Fetching metadata from {parser.__class__.__name__}...")
        try:
            result = parser.get_metadata(doi)
        except Exception as e:
            print(f"{parser.__class__.__name__} error: {e}")
            continue
        if not result.get("found"):
            continue
        sources.append(parser.__class__.__name__)
        for field, value in result.items():
            if field == "found" or value is None:
                continue
            if field not in merged or _better(value, merged[field]):
                merged[field] = value
    return {"found": bool(sources), "sources": sources} | merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--doi", required=True)
    parser.add_argument("--pdf-dir", default="pdf")
    parser.add_argument("--json-dir", default="json")
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    article_id = doi_to_id(args.doi)
    metadata = {"id": article_id} | fetch_all(args.doi)

    os.makedirs(args.json_dir, exist_ok=True)
    json_path = os.path.join(args.json_dir, f"{article_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Metadata saved: {json_path}")

    if not args.no_pdf:
        os.makedirs(args.pdf_dir, exist_ok=True)
        for p in PARSERS:
            try:
                if p.download_pdf(args.doi, args.pdf_dir):
                    path = os.path.join(args.pdf_dir, f"{doi_to_id(args.doi)}.pdf")
                    print(f"PDF saved: {path} ({os.path.getsize(path)} bytes)")
                    break
            except Exception as e:
                print(f"{p.__class__.__name__} PDF error: {e}")
        else:
            print("PDF download failed.")
