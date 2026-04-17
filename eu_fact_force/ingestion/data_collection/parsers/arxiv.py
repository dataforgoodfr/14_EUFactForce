import arxiv

from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser

ARXIV_DOI_PREFIX = "10.48550/arXiv."


class ArxivMetadataParser(MetadataParser):
    """Fetches metadata from the arXiv API. Only useful for arXiv preprints."""

    def __init__(self):
        super().__init__()
        self.api_name = "arxiv"
        self.client = arxiv.Client()

    def _search(self, doi: str):
        if doi.startswith(ARXIV_DOI_PREFIX):
            search = arxiv.Search(id_list=[doi[len(ARXIV_DOI_PREFIX):]])
        else:
            search = arxiv.Search(query=f"doi:{doi}", max_results=1)
        results = list(self.client.results(search))
        return results[0] if results else None

    def get_metadata(self, doi: str) -> dict:
        article = self._search(doi)
        if not article:
            return {"found": False}
        return {
            "found": True,
            "title": article.title,
            "authors": [{"name": str(a), "orcid": None} for a in article.authors],
            "journal": article.journal_ref,
            "publish date": str(article.published)[:10],
            "link": next(
                (link.href for link in article.links if link.rel == "alternate"), None
            ),
            "keywords": None,
            "cited articles": None,
            "doi": doi,
            "document type": None,
            "open access": True,
            "status": f"updated on {str(article.updated)[:10]}"
            if article.updated != article.published
            else "published",
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        article = self._search(doi)
        return [article.pdf_url] if article else []


if __name__ == "__main__":
    import json

    parser = ArxivMetadataParser()
    metadata = parser.get_metadata("10.48550/arXiv.2603.06740")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
