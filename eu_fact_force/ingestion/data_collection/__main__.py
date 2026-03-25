"""
CLI entry point. Usage:
    python -m eu_fact_force.ingestion.data_collection --doi 10.xxxx/yyyy
"""
import argparse
import json
import os

from .collector import fetch_all
from .parsers import PARSERS
from .parsers.base import doi_to_id

_BASE_DIR = os.path.dirname(__file__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doi", required=True)
    parser.add_argument("--pdf-dir", default=os.path.join(_BASE_DIR, "pdf"))
    parser.add_argument("--json-dir", default=os.path.join(_BASE_DIR, "json"))
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
                    path = os.path.join(
                        args.pdf_dir, f"{doi_to_id(args.doi)}_{p.api_name}.pdf"
                    )
                    print(f"PDF saved: {path} ({os.path.getsize(path)} bytes)")
                    break
            except Exception as e:
                print(f"{p.__class__.__name__} PDF error: {e}")
        else:
            print("PDF download failed.")


if __name__ == "__main__":
    main()
