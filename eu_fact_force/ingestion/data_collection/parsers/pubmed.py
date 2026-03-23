import requests

from parsers.base import MetadataParser

from utils import doi_to_id
import os



class PubMedMetadataParser(MetadataParser):
    """Fetches metadata from the PubMed API (https://eutils.ncbi.nlm.nih.gov)."""

    def __init__(self):
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def _resolve_pubmed_id(self, doi: str):
        response = requests.get(self.search_url, params={"db": "pubmed", "retmode": "json", "term": doi + "[DOI]"})
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None

    def _get_authors(self, doc):
        return [a.get("name") for a in doc.get("authors", []) if a.get("name")]

    def _get_doi(self, doc):
        return next((item["value"] for item in doc.get("articleids", []) if item.get("idtype") == "doi"), None)

    def get_metadata(self, doi: str) -> dict:
        pubmed_id = self._resolve_pubmed_id(doi)
        if not pubmed_id:
            return {"found": False}
        response = requests.get(self.summary_url, params={"db": "pubmed", "id": pubmed_id, "retmode": "json"})
        response.raise_for_status()
        doc = response.json().get("result", {}).get(pubmed_id)
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "article name": doc.get("title"),
            "authors": self._get_authors(doc),
            "journal": doc.get("fulljournalname"),
            "publish date": doc.get("pubdate"),
            "link": None,
            "keywords": None,
            "cited articles": None,
            "doi": self._get_doi(doc),
            "document type": doc.get("pubtype") or None,
            "open access": None,
            "status": "retracted" if "Retracted Publication" in doc.get("pubtype", []) else "published",
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        return []

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

    parser = PubMedMetadataParser()
    metadata = parser.get_metadata("10.1016/S0140-6736(97)11096-0")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
