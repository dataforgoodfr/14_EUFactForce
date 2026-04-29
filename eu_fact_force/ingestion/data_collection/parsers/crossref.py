import requests
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class CrossrefMetadataParser(MetadataParser):
    """Fetches metadata from the Crossref API (https://api.crossref.org)."""

    def __init__(self):
        super().__init__()
        self.url = "https://api.crossref.org/works/{doi}"
        self.session = requests.Session()
        self._cache = {}

    def _get_doc(self, doi: str):
        if doi not in self._cache:
            response = self.session.get(self.url.format(doi=doi), timeout=10)
            if response.status_code == 404:
                self._cache[doi] = None
            else:
                response.raise_for_status()
                self._cache[doi] = response.json().get("message", {})
        return self._cache[doi]

    def _get_authors(self, doc):
        return [
            {
                "name": f"{a.get('given', '')} {a.get('family', '')}".strip(),
                "orcid": a.get("ORCID", "").replace("http://orcid.org/", "").replace("https://orcid.org/", "") or None,
            }
            for a in doc.get("author", [])
        ]

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
        doc = self._get_doc(doi)
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "title": (doc.get("title") or [None])[0],
            "authors": self._get_authors(doc),
            "journal": {"name": doc.get("publisher"), "issn": (doc.get("ISSN") or [None])[0]},
            "publication date": self._get_publish_date(doc),
            "status": self._get_status(doc),
            "doi": doc.get("DOI"),
            "link": self._get_link(doc),
            "document type": doc.get("type"),
            "document subtypes": None,
            "open access": None,
            "language": doc.get("language"),
            "cited by count": None,
            "abstract": None,
            "keywords": None,
            "cited articles": self._get_cited_articles(doc),
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            doc = self._get_doc(doi)
            if not doc:
                return []
            for link in doc.get("link", []):
                if "pdf" in link.get("content-type", "") and link.get("URL"):
                    return [link["URL"]]
            return []
        except Exception as e:
            self.logger.error(f"CrossRef error: {e}")
            return []
