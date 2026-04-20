import requests
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class OpenAlexMetadataParser(MetadataParser):
    """Fetches metadata from the OpenAlex API (https://api.openalex.org)."""

    def __init__(self):
        super().__init__()
        self.url = "https://api.openalex.org/works/doi:{doi}"
        self.cited_articles_url = "https://api.openalex.org/works?filter=ids.openalex:{ids}&select=id,doi&per-page=200"
        self.session = requests.Session()
        self._cache = {}

    def _get_doc(self, doi: str):
        if doi not in self._cache:
            response = self.session.get(self.url.format(doi=doi), timeout=10)
            if response.status_code == 404:
                self._cache[doi] = None
            else:
                response.raise_for_status()
                self._cache[doi] = response.json()
        return self._cache[doi]

    def _get_authors(self, doc):
        return [
            {
                "name": a.get("raw_author_name"),
                "orcid": (a.get("author") or {}).get("orcid"),
            }
            for a in doc.get("authorships", [])
            if a.get("raw_author_name")
        ]

    def _get_journal(self, doc):
        source = (doc.get("primary_location") or {}).get("source") or {}
        return {
            "name": source.get("host_organization_name"),
            "issn": source.get("issn_l"),
        }

    def _get_link(self, doc):
        return (doc.get("primary_location") or {}).get("landing_page_url")

    def _get_keywords(self, doc):
        seen = set()
        result = []
        for item in doc.get("mesh", []):
            name = item.get("descriptor_name")
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return result or None

    def _get_cited_articles(self, doc):
        ids = [url.split("/")[-1] for url in doc.get("referenced_works", [])]
        if not ids:
            return []
        results = []
        for i in range(0, len(ids), 100):
            response = self.session.get(
                self.cited_articles_url.format(ids="|".join(ids[i: i + 100])),
                timeout=10,
            )
            response.raise_for_status()
            results += [
                r["doi"].removeprefix("https://doi.org/") for r in response.json().get("results", []) if r.get("doi")
            ]
        return results

    def _get_doi(self, doc):
        return (doc.get("doi") or "").removeprefix("https://doi.org/") or None

    def get_metadata(self, doi: str) -> dict:
        doc = self._get_doc(doi)
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "title": doc.get("title"),
            "authors": self._get_authors(doc),
            "journal": self._get_journal(doc),
            "publication date": doc.get("publication_date"),
            "status": "retracted" if doc.get("is_retracted") else "published",
            "doi": self._get_doi(doc),
            "link": self._get_link(doc),
            "document type": doc.get("type"),
            "document subtypes": None,
            "open access": (doc.get("open_access") or {}).get("is_oa"),
            "language": doc.get("language"),
            "cited by count": doc.get("cited_by_count"),
            "abstract": None,
            "keywords": self._get_keywords(doc),
            "cited articles": self._get_cited_articles(doc),
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            doc = self._get_doc(doi)
            if not doc:
                return []
            results = []
            for location in [doc.get("best_oa_location")] + doc.get("locations", []):
                url = (location or {}).get("pdf_url")
                if url and url not in results:
                    results.append(url)
            oa_url = (doc.get("open_access") or {}).get("oa_url")
            if oa_url and oa_url not in results:
                results.append(oa_url)
            return results
        except Exception as e:
            self.logger.error(f"OpenAlex error: {e}")
            return []
