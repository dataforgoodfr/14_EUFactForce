"""
Tests for seed database search module.
"""

import pytest

from eu_fact_force.ingestion.data_collection.search import (
    PubMedSearcher,
    CrossrefSearcher,
    ArticleSearcher,
    SearchResult,
)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_to_dict(self):
        result = SearchResult(
            doi="10.1234/test",
            title="Test Article",
            authors=["Author A", "Author B"],
            pub_date="2020-01-01",
            journal="Test Journal",
            source="pubmed",
            open_access=True,
        )
        d = result.to_dict()
        assert d["doi"] == "10.1234/test"
        assert d["title"] == "Test Article"
        assert d["open_access"] is True


class TestPubMedSearcher:
    """Test PubMed search functionality (integration tests)."""

    @pytest.mark.integration
    def test_pubmed_search_vaccine_autism(self):
        """Search PubMed for vaccine-autism articles."""
        searcher = PubMedSearcher()
        results = searcher.search(
            'vaccine AND autism AND ("refut*" OR "debunk*" OR "safe")',
            max_results=10,
        )
        assert len(results) > 0
        assert all(r.source == "pubmed" for r in results)
        assert all(r.doi is not None for r in results)

    @pytest.mark.integration
    def test_pubmed_search_with_year_filter(self):
        """Search PubMed with year filter."""
        searcher = PubMedSearcher()
        results = searcher.search(
            "vaccine autism",
            max_results=10,
            min_year=2015,
        )
        assert len(results) > 0
        # Note: year filtering is in the query, hard to verify without parsing dates


class TestCrossrefSearcher:
    """Test Crossref search functionality (integration tests)."""

    @pytest.mark.integration
    def test_crossref_search_vaccine_autism(self):
        """Search Crossref for vaccine-autism articles."""
        searcher = CrossrefSearcher()
        results = searcher.search("vaccine autism", max_results=10)
        assert len(results) > 0
        assert all(r.source == "crossref" for r in results)
        assert all(r.doi is not None for r in results)

    @pytest.mark.integration
    def test_crossref_search_open_access_only(self):
        """Search Crossref with open access filter."""
        searcher = CrossrefSearcher()
        results = searcher.search(
            "vaccine autism",
            max_results=10,
            open_access_only=True,
        )
        # Some results may be none, but those present should be True
        oa_results = [r for r in results if r.open_access is not None]
        if oa_results:
            assert all(r.open_access for r in oa_results)


class TestArticleSearcher:
    """Test orchestrated article search."""

    @pytest.mark.integration
    def test_article_searcher_deduplication(self):
        """Test that ArticleSearcher deduplicates across sources."""
        searcher = ArticleSearcher()
        result = searcher.search("vaccine autism", max_results=5)

        # Check structure
        assert "results" in result
        assert "summary" in result
        assert isinstance(result["results"], list)

        # All DOIs should be unique (case-insensitive)
        dois = [r.doi.lower() for r in result["results"]]
        assert len(dois) == len(set(dois)), "Duplicate DOIs found"

        # Summary should match
        assert result["summary"]["total_unique"] == len(result["results"])
        assert result["summary"]["query"] == "vaccine autism"


class TestSearchIntegration:
    """Integration tests for full search workflow."""

    @pytest.mark.integration
    def test_search_and_parse_results(self):
        """Test realistic search scenario."""
        searcher = ArticleSearcher()
        result = searcher.search(
            "vaccine autism refutation",
            max_results=15,
        )

        assert len(result["results"]) > 0

        # Check that results have required fields
        for r in result["results"]:
            assert r.doi is not None
            assert r.title
            assert r.source in ["pubmed", "crossref"]

        # Check summary
        summary = result["summary"]
        assert summary["total_unique"] > 0
        assert summary["pubmed_count"] >= 0
        assert summary["crossref_count"] >= 0
        assert summary["open_access_count"] >= 0
