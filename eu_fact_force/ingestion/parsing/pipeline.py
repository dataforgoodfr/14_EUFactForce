from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import structlog
from django.core.files.storage import default_storage

from eu_fact_force.ingestion.models import Document
from eu_fact_force.ingestion.parsing.docling_parser import ParseResult
from eu_fact_force.ingestion.parsing.docling_parser import parse_file as _parse_file_local
from eu_fact_force.utils.decorators import tracker

LOGGER = structlog.get_logger(__name__)


@contextmanager
def _source_file_local_path(source_file):
    """Yield a local file path for a source file stored in S3.

    S3 does not expose a filesystem path, so we stream the object into a temp
    file and yield that path. Downstream (e.g. Docling) expects a path to a
    real file on disk.
    """
    if not source_file.s3_key:
        raise ValueError("Cannot parse a source file without s3_key.")

    suffix = Path(source_file.s3_key).suffix
    with default_storage.open(source_file.s3_key, mode="rb") as handle:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(handle.read())
            tmp_path = Path(tmp.name)
    try:
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def _parse_source_file(source_file) -> ParseResult:
    with _source_file_local_path(source_file) as file_path:
        return _parse_file_local(file_path)


@tracker(ulogger=LOGGER, inputs=True, log_start=True)
def parse_file(document: Document) -> list[str]:
    """Parse the source file and return paragraph-bounded text chunks."""
    result = _parse_source_file(document.source_file)
    return result["chunks"]
