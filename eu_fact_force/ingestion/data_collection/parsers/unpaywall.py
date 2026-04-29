import os

import requests
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class UnpaywallMetadataParser(MetadataParser):
    """Fetches metadata from the Unpaywall API (https://api.unpaywall.org)."""

    def __init__(self):
        super().__init__()
        self.api_name = "unpaywall"
        self.url = "https://api.unpaywall.org/v2/{doi}?email={email}"
        self.session = requests.Session()
        self._cache = {}

    def _get_doc(self, doi: str):
        if doi not in self._cache:
            email = os.environ.get("UNPAYWALL_EMAIL", "")
            if not email:
                self.logger.warning("UNPAYWALL_EMAIL not set, skipping.")
                self._cache[doi] = None
            else:
                response = self.session.get(
                    self.url.format(doi=doi, email=email), timeout=10
                )
                if response.status_code == 404:
                    self._cache[doi] = None
                else:
                    response.raise_for_status()
                    self._cache[doi] = response.json() or None
        return self._cache[doi]

    def _get_link(self, doc):
        location = doc.get("best_oa_location") or {}
        return location.get("url_for_landing_page") or None

    def get_metadata(self, doi: str) -> dict:
        doc = self._get_doc(doi)
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "title": doc.get("title"),
            "authors": None,
            "journal": {"name": doc.get("journal_name"), "issn": doc.get("journal_issn_l")},
            "publication date": doc.get("published_date"),
            "status": None,
            "doi": doc.get("doi"),
            "link": self._get_link(doc),
            "document type": doc.get("genre"),
            "document subtypes": None,
            "open access": doc.get("is_oa"),
            "language": None,
            "cited by count": None,
            "abstract": None,
            "keywords": None,
            "cited articles": None,
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            doc = self._get_doc(doi)
            if not doc:
                return []
            results = []
            locations = [doc.get("best_oa_location")] + (doc.get("oa_locations") or [])
            for loc in locations:
                url = (loc or {}).get("url_for_pdf")
                if url and url not in results:
                    results.append(url)
            return results
        except Exception as e:
            self.logger.error(f"Unpaywall error: {e}")
            return []
