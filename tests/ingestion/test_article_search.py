"""
Unit tests for eu_fact_force.ingestion.data_collection.search

All HTTP calls are mocked — no real API requests are made.
"""

from unittest.mock import MagicMock, patch

import pytest

from eu_fact_force.ingestion.data_collection.search import (
    ArticleSearcher,
    CrossrefSearcher,
    PubMedSearcher,
    SearchResult,
    _crossref_year,
    _parse_year,
    _sort_key,
)


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

class TestSearchResult:
    def test_to_dict_roundtrip(self):
        r = SearchResult(
            doi="10.1000/xyz",
            title="Test",
            authors=["A", "B"],
            pub_year=2023,
            journal="Nature",
            source="pubmed",
            open_access=True,
            url="https://example.com",
        )
        d = r.to_dict()
        assert d["doi"] == "10.1000/xyz"
        assert d["authors"] == ["A", "B"]
        assert d["pub_year"] == 2023
        assert d["open_access"] is True

    def test_optional_fields_default_none(self):
        r = SearchResult("10.1/x", "T", [], None, None, "crossref")
        assert r.open_access is None
        assert r.url is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestParseYear:
    def test_standard_pubmed_date(self):
        assert _parse_year("2023 Jan 15") == 2023

    def test_year_only(self):
        assert _parse_year("2021") == 2021

    def test_empty(self):
        assert _parse_year("") is None

    def test_no_four_digit_token(self):
        assert _parse_year("Jan 15") is None


class TestCrossrefYear:
    def test_published_online(self):
        item = {"published-online": {"date-parts": [[2022, 3, 1]]}}
        assert _crossref_year(item) == 2022

    def test_published_print_fallback(self):
        item = {"published-print": {"date-parts": [[2021, 6]]}}
        assert _crossref_year(item) == 2021

    def test_missing_returns_none(self):
        assert _crossref_year({}) is None

    def test_empty_date_parts_returns_none(self):
        item = {"published-online": {"date-parts": [[]]}}
        assert _crossref_year(item) is None


class TestSortKey:
    def test_oa_sorts_before_non_oa(self):
        oa = SearchResult("10.1/a", "A", [], 2020, None, "pubmed", open_access=True)
        non_oa = SearchResult("10.1/b", "B", [], 2020, None, "pubmed", open_access=False)
        assert _sort_key(oa) < _sort_key(non_oa)

    def test_newer_sorts_before_older_within_same_oa_tier(self):
        newer = SearchResult("10.1/a", "A", [], 2023, None, "pubmed", open_access=True)
        older = SearchResult("10.1/b", "B", [], 2020, None, "pubmed", open_access=True)
        assert _sort_key(newer) < _sort_key(older)

    def test_none_year_sorts_last_within_tier(self):
        with_year = SearchResult("10.1/a", "A", [], 2020, None, "pubmed", open_access=False)
        no_year = SearchResult("10.1/b", "B", [], None, None, "pubmed", open_access=False)
        assert _sort_key(with_year) < _sort_key(no_year)


# ---------------------------------------------------------------------------
# PubMedSearcher
# ---------------------------------------------------------------------------

_PUBMED_SEARCH_RESPONSE = {
    "esearchresult": {"idlist": ["12345", "67890"]}
}

_PUBMED_SUMMARY_RESPONSE = {
    "result": {
        "uids": ["12345", "67890"],
        "12345": {
            "title": "Vaccine study one",
            "authors": [{"name": "Smith J"}],
            "pubdate": "2022 Mar",
            "fulljournalname": "NEJM",
            "articleids": [{"idtype": "doi", "value": "10.1000/abc"}],
        },
        "67890": {
            "title": "No DOI paper",
            "authors": [],
            "pubdate": "2021",
            "fulljournalname": "BMJ",
            "articleids": [],  # No DOI — must be skipped
        },
    }
}


def _mock_response(data: dict) -> MagicMock:
    r = MagicMock(status_code=200)
    r.json.return_value = data
    r.raise_for_status = MagicMock()
    return r


class TestPubMedSearcher:
    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_returns_only_results_with_doi(self, mock_get):
        mock_get.side_effect = [
            _mock_response(_PUBMED_SEARCH_RESPONSE),
            _mock_response(_PUBMED_SUMMARY_RESPONSE),
        ]
        results = PubMedSearcher().search("vaccine autism")
        assert len(results) == 1
        assert results[0].doi == "10.1000/abc"
        assert results[0].source == "pubmed"
        assert results[0].pub_year == 2022

    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_no_ids_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response({"esearchresult": {"idlist": []}})
        assert PubMedSearcher().search("nothing") == []

    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_network_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("network error")
        assert PubMedSearcher().search("vaccine") == []

    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_min_year_appended_to_query(self, mock_get):
        mock_get.return_value = _mock_response({"esearchresult": {"idlist": []}})
        PubMedSearcher().search("vaccine", min_year=2020)
        call_params = mock_get.call_args[1]["params"]
        assert "2020[PDAT]" in call_params["term"]


# ---------------------------------------------------------------------------
# CrossrefSearcher
# ---------------------------------------------------------------------------

_CROSSREF_RESPONSE = {
    "message": {
        "items": [
            {
                "DOI": "10.2000/def",
                "title": ["Crossref article"],
                "author": [{"given": "Jane", "family": "Doe"}],
                "published-online": {"date-parts": [[2023, 1, 10]]},
                "container-title": ["Journal of Science"],
                "is-oa": True,
            },
            {
                # No DOI — must be skipped
                "title": ["No DOI"],
                "author": [],
            },
        ]
    }
}


class TestCrossrefSearcher:
    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_returns_results_without_missing_doi(self, mock_get):
        mock_get.return_value = _mock_response(_CROSSREF_RESPONSE)
        results = CrossrefSearcher().search("vaccine autism")
        assert len(results) == 1
        assert results[0].doi == "10.2000/def"
        assert results[0].open_access is True
        assert results[0].pub_year == 2023
        assert results[0].authors == ["Jane Doe"]

    @patch("eu_fact_force.ingestion.data_collection.search.requests.get")
    def test_network_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        assert CrossrefSearcher().search("vaccine") == []


# ---------------------------------------------------------------------------
# ArticleSearcher — deduplication and sorting
# ---------------------------------------------------------------------------

class TestArticleSearcher:
    def _make(self, doi, source="pubmed", oa=False, year=2020):
        return SearchResult(doi, "Title", [], year, None, source, open_access=oa)

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_deduplicates_same_doi(self, mock_pm, mock_cr):
        doi = "10.1000/shared"
        mock_pm.return_value = [self._make(doi, "pubmed")]
        mock_cr.return_value = [self._make(doi, "crossref")]
        assert len(ArticleSearcher().search("q")) == 1

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_pubmed_wins_on_duplicate(self, mock_pm, mock_cr):
        doi = "10.1000/overlap"
        mock_pm.return_value = [self._make(doi, "pubmed")]
        mock_cr.return_value = [self._make(doi, "crossref")]
        assert ArticleSearcher().search("q")[0].source == "pubmed"

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_doi_dedup_is_case_insensitive(self, mock_pm, mock_cr):
        mock_pm.return_value = [self._make("10.1000/ABC", "pubmed")]
        mock_cr.return_value = [self._make("10.1000/abc", "crossref")]
        assert len(ArticleSearcher().search("q")) == 1

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_oa_sorted_first(self, mock_pm, mock_cr):
        mock_pm.return_value = [
            self._make("10.1/a", oa=False, year=2023),
            self._make("10.1/b", oa=True, year=2020),
        ]
        mock_cr.return_value = []
        results = ArticleSearcher().search("q")
        assert results[0].open_access is True

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_both_empty_returns_empty(self, mock_pm, mock_cr):
        mock_pm.return_value = []
        mock_cr.return_value = []
        assert ArticleSearcher().search("q") == []

    @patch.object(CrossrefSearcher, "search")
    @patch.object(PubMedSearcher, "search")
    def test_unique_dois_merged_from_both_sources(self, mock_pm, mock_cr):
        mock_pm.return_value = [self._make("10.1/a")]
        mock_cr.return_value = [self._make("10.1/b", "crossref")]
        assert len(ArticleSearcher().search("q")) == 2
