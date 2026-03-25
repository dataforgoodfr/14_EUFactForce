import requests

from .base import MetadataParser


class HALMetadataParser(MetadataParser):
    """Fetches metadata from the HAL open archive API (https://api.archives-ouvertes.fr)."""

    def __init__(self):
        super().__init__()
        self.api_name = "hal"
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
            docs = response.json().get("response", {}).get("docs", [])
            if not docs:
                return []
            uri = docs[0].get("uri_s")
            if not uri:
                return []
            return [f"{uri}/document"]
        except Exception as e:
            self.logger.error(f"HAL error: {e}")
            return []


if __name__ == "__main__":
    import json

    parser = HALMetadataParser()
    metadata = parser.get_metadata("10.26855/ijcemr.2021.01.001")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
