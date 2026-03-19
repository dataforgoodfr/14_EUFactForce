from metadata_parser import MetadataParser
import requests


class CrossrefMetadataParser(MetadataParser):
    def __init__(self):
        super().__init__()
        self.url = "https://api.crossref.org/works/{doi}"

    def _get_authors(self, doc):
        return [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in doc.get("author", [])
        ]

    def _get_publish_date(self, doc):
        date_parts = ((doc.get("published") or {}).get("date-parts") or [[]])[0]
        return "-".join(str(p) for p in date_parts) if date_parts else None

    def _get_link(self, doc):
        return (doc.get("resource") or {}).get("primary", {}).get("URL")

    def _get_cited_articles(self, doc):
        return [
            ref.get("DOI") or ref.get("unstructured")
            for ref in doc.get("reference", [])
        ]

    def _get_status(self, doc):
        updates = doc.get("updated-by") or []
        if updates:
            return [
                f"{u.get('type')} on {u.get('updated', {}).get('date-time', '')[:10]}"
                for u in updates
            ]
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
            "found":          True,
            "article name":   (doc.get("title") or [None])[0],
            "authors":        self._get_authors(doc),
            "journal":        doc.get("publisher"),
            "publish date":   self._get_publish_date(doc),
            "link":           self._get_link(doc),
            "keywords":       None,
            "cited articles": self._get_cited_articles(doc),
            "doi":            doc.get("DOI"),
            "article type":   doc.get("type"),
            "open access":    None,
            "status":         self._get_status(doc),
        }



if __name__ == "__main__":
    parser = CrossrefMetadataParser()
    doi = "10.1016/S0140-6736(97)11096-0"
    metadata = parser.get_metadata(doi)
    print(metadata)
