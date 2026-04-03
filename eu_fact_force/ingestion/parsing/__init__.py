"""Parsing package: Docling/postprocess pipeline and benchmark tooling."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from eu_fact_force.exploration.parsing_benchmarking.benchmarking.parsers import (
    parse_docling,
)
from eu_fact_force.ingestion.chunking import MAX_CHUNK_CHARS, split_into_paragraph_chunks
from django.core.files.storage import default_storage

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


def _extract_text_from_source_file(source_file) -> str:
    """Parse a source file with Docling and return postprocessed markdown text."""

    with _source_file_local_path(source_file) as file_path:
        full_text, _, _ = parse_docling(
            file_path=file_path,
            result_type="markdown",
            postprocess=True,
            validate_text_bboxes=True,
        )
    return full_text


def parse_file(source_file) -> list[str]:
    """
    Parse the source file and return paragraph-bounded text chunks.
    As a v0 we assume the chunks are the tags.
    """

    full_text = _extract_text_from_source_file(source_file)
    return split_into_paragraph_chunks(full_text, max_chunk_chars=MAX_CHUNK_CHARS)
