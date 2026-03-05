"""Parser adapter functions used by benchmark orchestration."""

from __future__ import annotations

from pathlib import Path

import fitz as PyMuPDF
from docling.document_converter import DocumentConverter
from hierarchical.postprocessor import ResultPostprocessor

from docling_postprocess import render_docling_output


def parse_llamaparse(file_path: Path, result_type: str, api_key: str | None):
    """Parse a PDF with LlamaParse and return (full_text, first_chunk, pages, num_docs)."""
    from llama_index.core import SimpleDirectoryReader
    from llama_index.readers.llama_parse import LlamaParse

    parser = LlamaParse(api_key=api_key, result_type=result_type)
    reader = SimpleDirectoryReader(
        input_files=[str(file_path)],
        file_extractor={".pdf": parser},
    )
    documents = reader.load_data()

    full_text = "\n".join(d.text for d in documents)
    first_chunk = documents[0].text if documents else ""

    if documents and "page_label" in documents[0].metadata:
        pages = len({d.metadata.get("page_label") for d in documents})
    else:
        pages = len(documents)

    return full_text, first_chunk, pages, len(documents)


def parse_pymupdf(file_path: Path):
    """Parse a PDF with PyMuPDF and return (full_text, first_chunk, pages, num_docs)."""
    doc = PyMuPDF.open(str(file_path))
    page_texts = [doc[i].get_text() for i in range(len(doc))]
    pages = len(doc)
    doc.close()

    full_text = "\n".join(page_texts)
    first_chunk = page_texts[0] if page_texts else ""
    return full_text, first_chunk, pages, pages  # one "document" per page


def parse_docling(
    file_path: Path,
    result_type: str,
    postprocess: bool,
    validate_text_bboxes: bool = True,
):
    """Parse a PDF with Docling and return (full_text, pages, num_docs)."""
    parser = DocumentConverter()
    result = parser.convert(file_path)
    if postprocess is True:
        ResultPostprocessor(result).process()
    doc_dict = result.document.export_to_dict()

    full_text, stats = render_docling_output(
        file_path=file_path,
        result=result,
        doc_dict=doc_dict,
        result_type=result_type,
        validate_text_bboxes=validate_text_bboxes,
    )
    if stats:
        print(
            "[docling-bbox-filter] "
            f"{file_path.name}: dropped {stats['dropped_text_blocks']}/"
            f"{stats['considered_text_blocks']} text blocks without real PDF words"
        )

    return full_text, len(result.pages), 1  # One PDF document per call


def parse_with_config(
    file_path: Path,
    config: dict[str, object],
    docling_validate_bboxes: bool,
    llamaparse_api_key: str | None,
) -> tuple[str, int, int]:
    """Dispatch to parser-specific adapter and normalize return fields."""
    parser_type = str(config["type"])
    if parser_type == "llamaparse":
        full_text, _, pages, num_docs = parse_llamaparse(
            file_path=file_path,
            result_type=str(config["result_type"]),
            api_key=llamaparse_api_key,
        )
    elif parser_type == "docling":
        full_text, pages, num_docs = parse_docling(
            file_path=file_path,
            result_type=str(config["result_type"]),
            postprocess=bool(config.get("postprocess", False)),
            validate_text_bboxes=docling_validate_bboxes,
        )
    else:
        full_text, _, pages, num_docs = parse_pymupdf(file_path=file_path)
    return full_text, pages, num_docs

