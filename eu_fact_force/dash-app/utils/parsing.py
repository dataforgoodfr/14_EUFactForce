import base64
from typing import Optional

from eu_fact_force.ingestion.pdf_utils import (
    extract_abstract_from_pdf,
    extract_authors_from_pdf,
    extract_date_from_pdf,
    extract_doi_from_pdf,
    extract_journal_from_pdf,
    extract_link_from_pdf,
    extract_text_by_blocks,
    extract_title_from_pdf,
)


def load_png_as_data_uri(png_path: str) -> Optional[str]:
    """Return a data URI for a PNG file, or None if not found."""
    try:
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png+xml;base64,{b64}"
    except FileNotFoundError:
        return None


def extract_pdf_metadata(uploaded_file) -> dict:
    """Extract metadata from an uploaded PDF file object."""
    metadata = {
        "title": None,
        "doi": None,
        "abstract": None,
        "publication_date": None,
        "journal": None,
        "article_link": None,
        "authors": [],
    }
    try:
        pdf_text = extract_text_by_blocks(uploaded_file.read())
        metadata["title"] = extract_title_from_pdf(pdf_text)
        metadata["doi"] = extract_doi_from_pdf(pdf_text)
        metadata["abstract"] = extract_abstract_from_pdf(pdf_text)
        metadata["authors"] = extract_authors_from_pdf(pdf_text)
        metadata["publication_date"] = extract_date_from_pdf(pdf_text)
        metadata["journal"] = extract_journal_from_pdf(pdf_text)
        metadata["article_link"] = extract_link_from_pdf(pdf_text, metadata["doi"])
    except Exception as e:
        print(f"Error processing PDF: {e}")
    return metadata
