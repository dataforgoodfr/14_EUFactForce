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
