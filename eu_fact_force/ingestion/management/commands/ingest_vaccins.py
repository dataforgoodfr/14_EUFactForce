"""
Ingest vaccins pipeline: read vaccins_annotated.json from S3 bucket performances,
download PDF + JSON per entry, run full pipeline (save to S3 + Postgres, parse, chunks, embeddings).
"""

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from eu_fact_force.ingestion.embedding import add_embeddings
from eu_fact_force.ingestion.parsing import parse_file
from eu_fact_force.ingestion.services import save_chunks, save_to_s3_and_postgres

logger = logging.getLogger(__name__)

PERFORMANCES_BUCKET_NAME = "performances"
VACCINS_ANNOTATED_KEY = "vaccins_annotated.json"
PDF_PREFIX = "pdf"


def fetch_annotated_list(s3_client) -> list[dict]:
    """Download and parse vaccins_annotated.json from bucket performances."""
    resp = s3_client.get_object(
        Bucket=PERFORMANCES_BUCKET_NAME,
        Key=VACCINS_ANNOTATED_KEY,
    )
    data = json.loads(resp["Body"].read().decode())
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {VACCINS_ANNOTATED_KEY}, got {type(data)}")
    return data


def download_pdf_and_json(s3_client, key: str, dest_dir: Path) -> tuple[Path, dict]:
    """
    Download pdf/<key>.pdf and pdf/<key>.json into dest_dir.
    Returns (path_to_pdf, path_to_json, tags_pubmed from JSON).
    Raises or logs on missing objects.
    """
    pdf_key = f"{key}.pdf"
    json_key = f"{key}.json"

    try:
        s3_client.head_object(Bucket=PERFORMANCES_BUCKET_NAME, Key=pdf_key)
    except s3_client.exceptions.ClientError:
        raise FileNotFoundError(f"S3 object not found: {pdf_key}")

    try:
        s3_client.head_object(Bucket=PERFORMANCES_BUCKET_NAME, Key=json_key)
    except s3_client.exceptions.ClientError:
        raise FileNotFoundError(f"S3 object not found: {json_key}")

    pdf_path = dest_dir / f"{key}.pdf"
    json_path = dest_dir / f"{key}.json"

    s3_client.download_file(PERFORMANCES_BUCKET_NAME, pdf_key, str(pdf_path))
    s3_client.download_file(PERFORMANCES_BUCKET_NAME, json_key, str(json_path))

    with open(json_path, encoding="utf-8") as f:
        metadata = json.load(f)
    return pdf_path, metadata


class Command(BaseCommand):
    help = (
        "Read vaccins_annotated.json from S3 bucket performances, "
        "download PDF + JSON per entry, run full ingestion pipeline."
    )

    def handle(self, *args, **options):
        performance_dir = Path(__file__).resolve().parents[4] / "data" / "vaccine_perfs"
        pdfs = list(performance_dir.glob("*.pdf"))
        for pdf_path in pdfs:
            logger.info(f"Processing {pdf_path.stem}")
            key = pdf_path.stem
            metadata = json.load(pdf_path.with_suffix(".json").open())
            source_file = save_to_s3_and_postgres(
                pdf_path,
                tags_pubmed=metadata.get("tags_pubmed", []),
                doi=key,
            )
            document_parts = parse_file(source_file)
            chunks = save_chunks(source_file, document_parts)
            add_embeddings(chunks)

        self.stdout.write(self.style.SUCCESS(f"Done. Processed: {len(pdfs)}"))
