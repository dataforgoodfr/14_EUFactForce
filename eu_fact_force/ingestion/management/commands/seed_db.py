import csv
import logging

from django.core.management.base import BaseCommand, CommandError

from eu_fact_force.ingestion.services import DuplicateDOIError, ingest_by_doi

logger = logging.getLogger(__name__)


def _parse_csv_rows(rows: list[dict], stderr_write) -> tuple[list[tuple[str, str | None]], int]:
    """Validate and deduplicate CSV rows. Skips rows with missing or duplicate DOIs (within the CSV only — DB-level duplicates are caught later by ingest_by_doi)."""
    seen_dois: set[str] = set()
    to_ingest: list[tuple[str, str | None]] = []
    skipped_no_doi = 0

    for i, row in enumerate(rows, start=2):
        doi = (row.get("doi") or "").strip()
        if not doi:
            stderr_write(f"Row {i}: missing doi — skipped")
            skipped_no_doi += 1
            continue
        if doi in seen_dois:
            stderr_write(f"Row {i}: duplicate doi '{doi}' in CSV — skipped")
            continue
        seen_dois.add(doi)
        pdf_url = (row.get("pdf_url") or "").strip() or None
        to_ingest.append((doi, pdf_url))

    return to_ingest, skipped_no_doi


class Command(BaseCommand):
    help = "Seed the database from a CSV of DOIs."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path to CSV file with a 'doi' column.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be ingested without writing to the database.",
        )

    def handle(self, *args, **options):
        self._handle_csv(options["csv"], options["dry_run"])

    def _handle_csv(self, csv_path: str, dry_run: bool) -> None:
        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if "doi" not in (reader.fieldnames or []):
                    raise CommandError(f"CSV must have a 'doi' column, got: {reader.fieldnames}")
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        to_ingest, skipped_no_doi = _parse_csv_rows(rows, self.stderr.write)

        if dry_run:
            self.stdout.write(f"Dry run — {len(to_ingest)} DOI(s) would be ingested:")
            for doi, pdf_url in to_ingest:
                suffix = f"  (pdf_url={pdf_url})" if pdf_url else ""
                self.stdout.write(f"  {doi}{suffix}")
            if skipped_no_doi:
                self.stdout.write(f"  ({skipped_no_doi} row(s) skipped: missing doi)")
            return

        self._run_ingestion(to_ingest, skipped_no_doi)

    def _run_ingestion(self, to_ingest: list, skipped_no_doi: int) -> None:
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
