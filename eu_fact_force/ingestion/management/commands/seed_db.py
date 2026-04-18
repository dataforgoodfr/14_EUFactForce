import csv
import logging
import re
import tempfile
import zipfile
from pathlib import Path

import fitz
from django.core.management.base import BaseCommand, CommandError

from eu_fact_force.ingestion.services import DuplicateDOIError, ingest_by_doi

logger = logging.getLogger(__name__)


def _extract_doi_from_pdf(pdf_path: Path) -> str | None:
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc[:3]:
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
        for block in blocks:
            text += block[4] + "\n"

    match = re.search(r'(?:doi[:\s]+)?(?:https?://)?(?:dx\.)?doi\.org/(10\.\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1).rstrip(".,;)")

    match = re.search(r'10\.\d{4,}/\S+', text)
    if match:
        return match.group(0).rstrip(".,;)")

    return None


class Command(BaseCommand):
    help = "Seed the database from a CSV of DOIs or a zip archive of PDFs."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--csv", help="Path to CSV file with a 'doi' column.")
        group.add_argument("--zip", help="Path to zip archive of PDFs to ingest.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be ingested without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if options["csv"]:
            self._handle_csv(options["csv"], dry_run)
        else:
            self._handle_zip(options["zip"], dry_run)

    def _handle_csv(self, csv_path: str, dry_run: bool) -> None:
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
            to_ingest.append((doi, pdf_url, None))

        if dry_run:
            self.stdout.write(f"Dry run — {len(to_ingest)} DOI(s) would be ingested:")
            for doi, pdf_url, _ in to_ingest:
                suffix = f"  (pdf_url={pdf_url})" if pdf_url else ""
                self.stdout.write(f"  {doi}{suffix}")
            if skipped_no_doi:
                self.stdout.write(f"  ({skipped_no_doi} row(s) skipped: missing doi)")
            return

        self._run_ingestion(to_ingest, skipped_no_doi)

    def _handle_zip(self, zip_path: str, dry_run: bool) -> None:
        if not Path(zip_path).exists():
            raise CommandError(f"File not found: {zip_path}")

        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp)

            pdfs = sorted(Path(tmp).rglob("*.pdf"))
            to_ingest = []

            for pdf_path in pdfs:
                doi = _extract_doi_from_pdf(pdf_path)
                if doi is None:
                    self.stderr.write(f"{pdf_path.name}: could not extract DOI — skipped")
                    continue
                to_ingest.append((doi, None, pdf_path))

            if dry_run:
                self.stdout.write(f"Dry run — {len(to_ingest)} PDF(s) would be ingested:")
                for doi, _, pdf_path in to_ingest:
                    self.stdout.write(f"  {pdf_path.name} → {doi}")
                skipped = len(pdfs) - len(to_ingest)
                if skipped:
                    self.stdout.write(f"  ({skipped} PDF(s) skipped: no DOI found)")
                return

            skipped_no_doi = len(pdfs) - len(to_ingest)
            self._run_ingestion(to_ingest, skipped_no_doi)

    def _run_ingestion(self, to_ingest: list, skipped_no_doi: int) -> None:
        ingested = 0
        duplicates = 0
        errors = 0

        for doi, pdf_url, pdf_path in to_ingest:
            try:
                ingest_by_doi(doi, pdf_url=pdf_url, pdf_path=pdf_path)
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
