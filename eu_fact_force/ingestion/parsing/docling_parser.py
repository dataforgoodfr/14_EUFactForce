"""Production Docling parsing module for ingestion."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import TypedDict

from docling.document_converter import DocumentConverter
from hierarchical.postprocessor import ResultPostprocessor

from eu_fact_force.ingestion.chunking import MAX_CHUNK_CHARS, split_into_paragraph_chunks
from eu_fact_force.ingestion.parsing.docling_postprocess import render_docling_output


class ParseResult(TypedDict):
    postprocessed_text: str
    docling_output: dict
    parser_config: dict
    chunks: list[str]


def parse_file(
    file_path: Path,
    *,
    result_type: str = "markdown",
    postprocess: bool = True,
    validate_text_bboxes: bool = True,
) -> ParseResult:
    """Parse a local PDF with Docling and return a structured result.

    Args:
        file_path: Path to the local PDF file.
        result_type: Export format for the postprocessed text ("markdown" or "text").
        postprocess: Whether to apply hierarchical postprocessing.
        validate_text_bboxes: Whether to drop text blocks without real PDF words.

    Returns:
        ParseResult with postprocessed_text, docling_output, parser_config, and chunks.
    """
    converter = DocumentConverter()
    result = converter.convert(file_path)
    if postprocess:
        ResultPostprocessor(result).process()

    doc_dict = result.document.export_to_dict()

    full_text, stats = render_docling_output(
        file_path=file_path,
        result=result,
        doc_dict=doc_dict,
        result_type=result_type,
        validate_text_bboxes=validate_text_bboxes,
    )

    chunks = split_into_paragraph_chunks(full_text, max_chunk_chars=MAX_CHUNK_CHARS)

    parser_config: dict = {
        "docling_version": importlib.metadata.version("docling"),
        "result_type": result_type,
        "postprocess": postprocess,
        "validate_text_bboxes": validate_text_bboxes,
    }
    if stats:
        parser_config["bbox_filter_stats"] = stats

    return ParseResult(
        postprocessed_text=full_text,
        docling_output=doc_dict,
        parser_config=parser_config,
        chunks=chunks,
    )
