from xml.etree import ElementTree as ET

import requests
from utils import doi_to_id
import os

from parsers.base import MetadataParser


class HALMetadataParser(MetadataParser):
    """Fetches metadata from the HAL open archive API (https://api.archives-ouvertes.fr)."""

    def __init__(self):
        self.url = "https://api.archives-ouvertes.fr/search/?q=doiId_s:{doi}&fl=*"

    def _get_type(self, doc):
        return {"ART": "article", "THESIS": "thesis", "REPORT": "report"}.get(
            doc.get("docType_s"), doc.get("docType_s")
        )

    def _get_keywords(self, doc):
        return next((doc[key] for key in ["mesh_s", "keyword_s"] if doc.get(key)), None)

    def get_metadata(self, doi: str) -> dict:
        response = requests.get(self.url.format(doi=doi))
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        if not docs:
            return {"found": False}
        doc = docs[0]
        return {
            "found": True,
            "article name": doc.get("title_s"),
            "authors": doc.get("authFullName_s"),
            "journal": doc.get("journalTitle_s"),
            "publish date": doc.get("publicationDate_s"),
            "link": doc.get("uri_s"),
            "keywords": self._get_keywords(doc),
            "cited articles": None,
            "doi": doc.get("doiId_s"),
            "document type": self._get_type(doc),
            "open access": doc.get("openAccess_bool"),
            "status": None,
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            response = requests.get(self.url.format(doi=doi), timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            if int(root.find(".//result").get("numFound", "0")) == 0:
                return []
            uri_el = root.find(".//str[@name='uri_s']")
            if uri_el is None or not uri_el.text:
                return []
            return [f"{uri_el.text}/document"]
        except Exception as e:
            print(f"HAL error: {e}")
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

    parser = HALMetadataParser()
    metadata = parser.get_metadata("10.26855/ijcemr.2021.01.001")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
