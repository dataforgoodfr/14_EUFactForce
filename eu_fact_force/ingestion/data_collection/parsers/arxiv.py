import arxiv
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser

ARXIV_DOI_PREFIX = "10.48550/arXiv."


class ArxivMetadataParser(MetadataParser):
    """Fetches metadata from the arXiv API. Only useful for arXiv preprints."""

    def __init__(self):
        super().__init__()
        self.client = arxiv.Client()
        self._cache = {}

    def _search(self, doi: str):
        if doi not in self._cache:
            if doi.startswith(ARXIV_DOI_PREFIX):
                search = arxiv.Search(id_list=[doi[len(ARXIV_DOI_PREFIX):]])
            else:
                search = arxiv.Search(query=f"doi:{doi}", max_results=1)
            results = list(self.client.results(search))
            self._cache[doi] = results[0] if results else None
        return self._cache[doi]

    def get_metadata(self, doi: str) -> dict:
        article = self._search(doi)
        if not article:
            return {"found": False}
        return {
            "found": True,
            "title": article.title,
            "authors": [{"name": str(a), "orcid": None} for a in article.authors],
            "journal": {"name": article.journal_ref, "issn": None},
            "publication date": str(article.published)[:10],
            "status": f"updated on {str(article.updated)[:10]}"
            if article.updated != article.published
            else "published",
            "doi": doi,
            "link": next((link.href for link in article.links if link.rel == "alternate"), None),
            "document type": None,
            "document subtypes": None,
            "open access": True,
            "language": None,
            "cited by count": None,
            "abstract": article.summary,
            "keywords": None,
            "cited articles": None,
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        article = self._search(doi)
        return [article.pdf_url] if article else []
