"""Integration tests for metadata parsers and PDF download."""
import json
import os
from pathlib import Path

import pytest

from eu_fact_force.ingestion.data_collection.parsers.arxiv import ArxivMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.crossref import CrossrefMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.hal import HALMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.openalex import OpenAlexMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.pubmed import PubMedMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.unpaywall import UnpaywallMetadataParser

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"

TARGET_DOI = {
    "crossref": {
        "metadata": "10.1128/mbio.01735-25",
        "pdf": "10.1007/s00431-021-04343-1"
    },
    "openalex": "10.1371/journal.pone.0003140",
    "pubmed": "10.1177/2515690X20967323",
    "hal": "10.2196/39220",
    "arxiv": "10.48550/arXiv.2104.10635",
    "unpaywall": "10.31234/osf.io/tg7xr",
    "fake": "10.0000/does.not.exist",
}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

METADATA_SCHEMA = {
    "found":             bool,
    "title":             str,
    "authors":           list,
    "journal":           dict,
    "publication date":      str,
    "status":            (str, list),
    "doi":               str,
    "link":              str,
    "document type":     str,
    "document subtypes": list,
    "open access":       bool,
    "language":          str,
    "cited by count":    int,
    "abstract":          str,
    "keywords":          list,
    "cited articles":    list,
}

AUTHOR_SCHEMA = {"name": str, "orcid": str}
JOURNAL_SCHEMA = {"name": str, "issn": str}


def _check_schema(obj, schema, context=""):
    for field, expected_type in schema.items():
        assert field in obj, f"{context}missing field '{field}'"
        value = obj[field]
        if field == "found":
            assert isinstance(value, expected_type), (
                f"{context}'{field}' must be {expected_type}, got {type(value).__name__}"
            )
        elif value is not None:
            assert isinstance(value, expected_type), (
                f"{context}'{field}' expected {expected_type}, "
                f"got {type(value).__name__} = {value!r}"
            )


def assert_valid_metadata(result):
    assert result.get("found") is True
    _check_schema(result, METADATA_SCHEMA)
    if result.get("journal") is not None:
        _check_schema(result["journal"], JOURNAL_SCHEMA, context="journal.")
    if result.get("authors"):
        for i, author in enumerate(result["authors"]):
            _check_schema(author, AUTHOR_SCHEMA, context=f"authors[{i}].")
    if result.get("cited articles") is not None:
        for ref in result["cited articles"]:
            assert isinstance(ref, str), f"cited article should be str, got {type(ref)}"
    if result.get("keywords") is not None:
        for kw in result["keywords"]:
            assert isinstance(kw, str), f"keyword should be str, got {type(kw)}"
    if result.get("document subtypes") is not None:
        for sub in result["document subtypes"]:
            assert isinstance(sub, str), f"document subtype should be str, got {type(sub)}"


def _expected(name):
    with open(FIXTURES / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

class TestCrossrefMetadataParser:
    def setup_method(self):
        self.parser = CrossrefMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(TARGET_DOI["crossref"]["metadata"])
        assert_valid_metadata(result)
        assert result == _expected("crossref_expected.json")

    def test_unknown_doi(self):
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False

    def test_download_pdf(self, tmp_path):
        success = self.parser.download_pdf(TARGET_DOI["crossref"]["pdf"], output_dir=str(tmp_path))
        assert success
        pdfs = list(tmp_path.glob("*.pdf"))
        assert pdfs and pdfs[0].stat().st_size > 0


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

class TestOpenAlexMetadataParser:
    def setup_method(self):
        self.parser = OpenAlexMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(TARGET_DOI["openalex"])
        assert_valid_metadata(result)
        assert result == _expected("openalex_expected.json")

    def test_unknown_doi(self):
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False

    def test_download_pdf(self, tmp_path):
        success = self.parser.download_pdf(TARGET_DOI["openalex"], output_dir=str(tmp_path))
        assert success
        pdfs = list(tmp_path.glob("*.pdf"))
        assert pdfs and pdfs[0].stat().st_size > 0


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------

class TestPubMedMetadataParser:
    def setup_method(self):
        self.parser = PubMedMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(TARGET_DOI["pubmed"])
        assert_valid_metadata(result)
        assert result == _expected("pubmed_expected.json")

    def test_unknown_doi(self):
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False


# ---------------------------------------------------------------------------
# HAL
# ---------------------------------------------------------------------------

class TestHALMetadataParser:
    def setup_method(self):
        self.parser = HALMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(TARGET_DOI["hal"])
        assert_valid_metadata(result)
        assert result == _expected("hal_expected.json")

    def test_unknown_doi(self):
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False

    def test_download_pdf(self, tmp_path):
        success = self.parser.download_pdf(TARGET_DOI["hal"], output_dir=str(tmp_path))
        assert success
        pdfs = list(tmp_path.glob("*.pdf"))
        assert pdfs and pdfs[0].stat().st_size > 0


# ---------------------------------------------------------------------------
# ArXiv
# ---------------------------------------------------------------------------

class TestArxivMetadataParser:
    def setup_method(self):
        self.parser = ArxivMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(TARGET_DOI["arxiv"])
        assert_valid_metadata(result)
        assert result == _expected("arxiv_expected.json")

    def test_unknown_doi(self):
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False

    def test_download_pdf(self, tmp_path):
        success = self.parser.download_pdf(TARGET_DOI["arxiv"], output_dir=str(tmp_path))
        assert success
        pdfs = list(tmp_path.glob("*.pdf"))
        assert pdfs and pdfs[0].stat().st_size > 0


# ---------------------------------------------------------------------------
# Unpaywall
# ---------------------------------------------------------------------------

class TestUnpaywallMetadataParser:
    def setup_method(self):
        self.parser = UnpaywallMetadataParser()

    def test_known_doi(self):
        if not os.environ.get("UNPAYWALL_EMAIL"):
            pytest.skip("UNPAYWALL_EMAIL not set")
        result = self.parser.get_metadata(TARGET_DOI["unpaywall"])
        assert_valid_metadata(result)
        assert result == _expected("unpaywall_expected.json")

    def test_unknown_doi(self):
        if not os.environ.get("UNPAYWALL_EMAIL"):
            pytest.skip("UNPAYWALL_EMAIL not set")
        assert self.parser.get_metadata(TARGET_DOI["fake"])["found"] is False

    def test_download_pdf(self, tmp_path):
        if not os.environ.get("UNPAYWALL_EMAIL"):
            pytest.skip("UNPAYWALL_EMAIL not set")
        success = self.parser.download_pdf(TARGET_DOI["unpaywall"], output_dir=str(tmp_path))
        assert success
        pdfs = list(tmp_path.glob("*.pdf"))
        assert pdfs and pdfs[0].stat().st_size > 0
