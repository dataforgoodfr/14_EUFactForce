import requests
import os
from utils import doi_to_id

from parsers.base import MetadataParser


class CrossrefMetadataParser(MetadataParser):
    """Fetches metadata from the Crossref API (https://api.crossref.org)."""

    def __init__(self):
        self.url = "https://api.crossref.org/works/{doi}"

    def _get_authors(self, doc):
        return [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in doc.get("author", [])]

    def _get_publish_date(self, doc):
        date_parts = ((doc.get("published") or {}).get("date-parts") or [[]])[0]
        return "-".join(str(p) for p in date_parts) if date_parts else None

    def _get_link(self, doc):
        return (doc.get("resource") or {}).get("primary", {}).get("URL")

    def _get_cited_articles(self, doc):
        results = []
        for ref in doc.get("reference", []):
            if ref.get("DOI"):
                results.append(ref["DOI"])
            elif ref.get("unstructured"):
                results.append(ref["unstructured"])
            else:
                title = ref.get("article-title") or ref.get("volume-title")
                if title:
                    parts = [title]
                    if ref.get("author"):
                        parts.append(ref["author"])
                    if ref.get("year"):
                        parts.append(f"({ref['year']})")
                    results.append(" ".join(parts))
        return results

    def _get_status(self, doc):
        updates = doc.get("updated-by") or []
        if updates:
            return [f"{u.get('type')} on {u.get('updated', {}).get('date-time', '')[:10]}" for u in updates]
        return "published"

    def get_metadata(self, doi: str) -> dict:
        response = requests.get(self.url.format(doi=doi))
        if response.status_code == 404:
            return {"found": False}
        response.raise_for_status()
        doc = response.json().get("message", {})
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "article name": (doc.get("title") or [None])[0],
            "authors": self._get_authors(doc),
            "journal": doc.get("publisher"),
            "publish date": self._get_publish_date(doc),
            "link": self._get_link(doc),
            "keywords": None,
            "cited articles": self._get_cited_articles(doc),
            "doi": doc.get("DOI"),
            "document type": doc.get("type"),
            "open access": None,
            "status": self._get_status(doc),
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            response = requests.get(self.url.format(doi=doi), timeout=10)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            for link in response.json().get("message", {}).get("link", []):
                if "pdf" in link.get("content-type", "") and link.get("URL"):
                    return [link["URL"]]
            return []
        except Exception as e:
            print(f"CrossRef error: {e}")
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

    parser = CrossrefMetadataParser()
    metadata = parser.get_metadata("10.1016/S0140-6736(97)11096-0")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
