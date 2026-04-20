import requests
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class HALMetadataParser(MetadataParser):
    """Fetches metadata from the HAL open archive API (https://api.archives-ouvertes.fr)."""

    def __init__(self):
        super().__init__()
        self.url = "https://api.archives-ouvertes.fr/search/?q=doiId_s:{doi}&fl=*"
        self.session = requests.Session()
        self._cache = {}

    def _get_docs(self, doi: str):
        if doi not in self._cache:
            response = self.session.get(self.url.format(doi=doi), timeout=10)
            response.raise_for_status()
            self._cache[doi] = response.json().get("response", {}).get("docs", [])
        return self._cache[doi]

    def _get_type(self, doc):
        return {"ART": "article", "THESIS": "thesis", "REPORT": "report"}.get(
            doc.get("docType_s"), doc.get("docType_s")
        )

    def _get_keywords(self, doc):
        return next((doc[key] for key in ["mesh_s", "keyword_s"] if doc.get(key)), None)

    def get_metadata(self, doi: str) -> dict:
        docs = self._get_docs(doi)
        if not docs:
            return {"found": False}
        doc = docs[0]
        names = doc.get("authFullName_s") or []
        orcids = doc.get("authORCIDIdExt_s") or []
        return {
            "found": True,
            "title": (doc.get("title_s") or [None])[0],
            "authors": [
                {"name": name, "orcid": orcids[i] if i < len(orcids) else None} for i, name in enumerate(names)
            ],
            "journal": {"name": doc.get("journalTitle_s"), "issn": doc.get("journalIssn_s")},
            "publication date": doc.get("publicationDate_s"),
            "status": None,
            "doi": doc.get("doiId_s"),
            "link": doc.get("uri_s"),
            "document type": self._get_type(doc),
            "document subtypes": None,
            "open access": doc.get("openAccess_bool"),
            "language": (doc.get("language_s") or [None])[0],
            "cited by count": None,
            "abstract": (doc.get("abstract_s") or [None])[0],
            "keywords": self._get_keywords(doc),
            "cited articles": None,
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            docs = self._get_docs(doi)
            if not docs:
                return []
            uri = docs[0].get("uri_s")
            if not uri:
                return []
            return [f"{uri}/document"]
        except Exception as e:
            self.logger.error(f"HAL error: {e}")
            return []
