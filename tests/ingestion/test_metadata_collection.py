"""Integration tests for metadata parsers against real APIs."""
import os

import pytest

from eu_fact_force.ingestion.data_collection.parsers.arxiv import ArxivMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.crossref import CrossrefMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.hal import HALMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.openalex import OpenAlexMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.pubmed import PubMedMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.unpaywall import UnpaywallMetadataParser

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

METADATA_SCHEMA = {
    "found":             bool,
    "article name":      str,
    "authors":           list,
    "journal":           dict,
    "publish date":      str,
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


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

CROSSREF_DOI = "10.1371/journal.pone.0003140"
CROSSREF_EXPECTED = {
    "doi": "10.1371/journal.pone.0003140",
    "article name contains": "measles",
    "journal issn": "1932-6203",
    "min authors": 1,
    "min cited articles": 1,
}


class TestCrossrefMetadataParser:
    def setup_method(self):
        self.parser = CrossrefMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(CROSSREF_DOI)
        assert_valid_metadata(result)
        assert result["doi"] == CROSSREF_EXPECTED["doi"]
        assert CROSSREF_EXPECTED["article name contains"] in result["article name"].lower()
        assert result["journal"]["issn"] == CROSSREF_EXPECTED["journal issn"]
        assert len(result["authors"]) >= CROSSREF_EXPECTED["min authors"]
        assert len(result["cited articles"]) >= CROSSREF_EXPECTED["min cited articles"]

    def test_unknown_doi(self):
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

OPENALEX_DOI = "10.1371/journal.pone.0003140"
OPENALEX_EXPECTED = {
    "doi": "10.1371/journal.pone.0003140",
    "article name contains": "measles",
    "min cited by count": 1,
    "min authors": 1,
}


class TestOpenAlexMetadataParser:
    def setup_method(self):
        self.parser = OpenAlexMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(OPENALEX_DOI)
        assert_valid_metadata(result)
        assert result["doi"] == OPENALEX_EXPECTED["doi"]
        assert OPENALEX_EXPECTED["article name contains"] in result["article name"].lower()
        assert result["cited by count"] >= OPENALEX_EXPECTED["min cited by count"]
        assert len(result["authors"]) >= OPENALEX_EXPECTED["min authors"]

    def test_unknown_doi(self):
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------

PUBMED_DOI = "10.1371/journal.pone.0003140"
PUBMED_EXPECTED = {
    "article name contains": "measles",
    "journal issn": "1932-6203",
    "language": "eng",
    "min authors": 1,
    "min keywords": 1,
}


class TestPubMedMetadataParser:
    def setup_method(self):
        self.parser = PubMedMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(PUBMED_DOI)
        assert_valid_metadata(result)
        assert PUBMED_EXPECTED["article name contains"] in result["article name"].lower()
        assert result["journal"]["issn"] == PUBMED_EXPECTED["journal issn"]
        assert result["language"] == PUBMED_EXPECTED["language"]
        assert result["abstract"] is not None and len(result["abstract"]) > 0
        assert len(result["authors"]) >= PUBMED_EXPECTED["min authors"]
        assert len(result["keywords"]) >= PUBMED_EXPECTED["min keywords"]

    def test_unknown_doi(self):
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False


# ---------------------------------------------------------------------------
# HAL
# ---------------------------------------------------------------------------

HAL_DOI = "10.26855/ijcemr.2021.01.001"
HAL_EXPECTED = {
    "doi": "10.26855/ijcemr.2021.01.001",
    "min authors": 1,
}


class TestHALMetadataParser:
    def setup_method(self):
        self.parser = HALMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(HAL_DOI)
        assert_valid_metadata(result)
        assert result["doi"] == HAL_EXPECTED["doi"]
        assert len(result["authors"]) >= HAL_EXPECTED["min authors"]

    def test_unknown_doi(self):
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False


# ---------------------------------------------------------------------------
# ArXiv
# ---------------------------------------------------------------------------

ARXIV_DOI = "10.48550/arXiv.2603.06740"
ARXIV_EXPECTED = {
    "doi": "10.48550/arXiv.2603.06740",
    "open access": True,
    "min authors": 1,
}


class TestArxivMetadataParser:
    def setup_method(self):
        self.parser = ArxivMetadataParser()

    def test_known_doi(self):
        result = self.parser.get_metadata(ARXIV_DOI)
        assert_valid_metadata(result)
        assert result["doi"] == ARXIV_EXPECTED["doi"]
        assert result["open access"] is ARXIV_EXPECTED["open access"]
        assert result["abstract"] is not None and len(result["abstract"]) > 0
        assert len(result["authors"]) >= ARXIV_EXPECTED["min authors"]

    def test_unknown_doi(self):
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False


# ---------------------------------------------------------------------------
# Unpaywall
# ---------------------------------------------------------------------------

UNPAYWALL_DOI = "10.1371/journal.pone.0003140"
UNPAYWALL_EXPECTED = {
    "article name contains": "measles",
    "journal issn": "1932-6203",
}


class TestUnpaywallMetadataParser:
    def setup_method(self):
        self.parser = UnpaywallMetadataParser()

    def test_known_doi(self):
        if not os.environ.get("UNPAYWALL_EMAIL"):
            pytest.skip("UNPAYWALL_EMAIL not set")
        result = self.parser.get_metadata(UNPAYWALL_DOI)
        assert_valid_metadata(result)
        assert UNPAYWALL_EXPECTED["article name contains"] in result["article name"].lower()
        assert result["journal"]["issn"] == UNPAYWALL_EXPECTED["journal issn"]

    def test_unknown_doi(self):
        if not os.environ.get("UNPAYWALL_EMAIL"):
            pytest.skip("UNPAYWALL_EMAIL not set")
        assert self.parser.get_metadata("10.0000/does.not.exist")["found"] is False
