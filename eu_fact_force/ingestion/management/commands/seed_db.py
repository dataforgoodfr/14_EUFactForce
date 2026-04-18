import csv
import logging

from django.core.management.base import BaseCommand, CommandError

from eu_fact_force.ingestion.services import DuplicateDOIError, ingest_by_doi

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Read a CSV of DOIs and ingest each one via ingest_by_doi."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path to CSV file with a 'doi' column.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print DOIs that would be ingested without writing to the database.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]
        dry_run = options["dry_run"]

        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if "doi" not in (reader.fieldnames or []):
                    raise CommandError(f"CSV must have a 'doi' column, got: {reader.fieldnames}")
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        seen_dois = set()
        to_ingest = []
        skipped_no_doi = 0

        for i, row in enumerate(rows, start=2):
            doi = (row.get("doi") or "").strip()
            if not doi:
                self.stderr.write(f"Row {i}: missing doi — skipped")
                skipped_no_doi += 1
                continue
            if doi in seen_dois:
                self.stderr.write(f"Row {i}: duplicate doi '{doi}' in CSV — skipped")
                continue
            seen_dois.add(doi)
            pdf_url = (row.get("pdf_url") or "").strip() or None
            to_ingest.append((doi, pdf_url))

        if dry_run:
            self.stdout.write(f"Dry run — {len(to_ingest)} DOI(s) would be ingested:")
            for doi, pdf_url in to_ingest:
                suffix = f"  (pdf_url={pdf_url})" if pdf_url else ""
                self.stdout.write(f"  {doi}{suffix}")
            if skipped_no_doi:
                self.stdout.write(f"  ({skipped_no_doi} row(s) skipped: missing doi)")
            return

        ingested = 0
        duplicates = 0
        errors = 0

        for doi, pdf_url in to_ingest:
            try:
                ingest_by_doi(doi, pdf_url=pdf_url)
                ingested += 1
                self.stdout.write(f"Ingested: {doi}")
            except DuplicateDOIError:
                duplicates += 1
                self.stderr.write(f"Duplicate (already in DB): {doi}")
            except Exception as exc:
                errors += 1
                self.stderr.write(f"Error ingesting '{doi}': {exc}")
                logger.exception("Ingestion failed for DOI %s", doi)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. ingested={ingested} duplicates={duplicates} errors={errors} skipped_no_doi={skipped_no_doi}"
            )
        )
