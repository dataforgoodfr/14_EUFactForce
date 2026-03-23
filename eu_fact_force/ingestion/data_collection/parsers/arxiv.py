import arxiv
import requests
from utils import doi_to_id
import os

from parsers.base import MetadataParser

ARXIV_DOI_PREFIX = "10.48550/arXiv."


class ArxivMetadataParser(MetadataParser):
    """Fetches metadata from the arXiv API. Only useful for arXiv preprints."""

    def __init__(self):
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
            "article name": article.title,
            "authors": [str(a) for a in article.authors],
            "journal": article.journal_ref,
            "publish date": str(article.published)[:10],
            "link": next((link.href for link in article.links if link.rel == "alternate"), None),
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

    def download_pdf(self, doi: str, output_dir: str = "pdf") -> bool:
        """Download the first valid PDF found and save it to output_dir. Returns True on success."""
        output_path = os.path.join(output_dir, f"{doi_to_id(doi)}.pdf")
        pdf_urls = self.get_pdf_url(doi)
        if not pdf_urls:
            return False
        try:
            for pdf_url in pdf_urls:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()
                if not response.content.startswith(b"%PDF"):
                    print(f"Content at {pdf_url} is not a valid PDF (possibly a paywall page).")
                    continue
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Download failed: {e}")
            return False


if __name__ == "__main__":
    import json

    parser = ArxivMetadataParser()
    metadata = parser.get_metadata("10.48550/arXiv.2603.06740")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
