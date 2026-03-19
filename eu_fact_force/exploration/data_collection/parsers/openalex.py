import requests

from parsers.base import MetadataParser


class OpenAlexMetadataParser(MetadataParser):
    """Fetches metadata from the OpenAlex API (https://api.openalex.org)."""

    def __init__(self):
        self.url = "https://api.openalex.org/works/doi:{doi}"
        self.cited_articles_url = "https://api.openalex.org/works?filter=ids.openalex:{ids}&select=id,doi&per-page=200"

    def _get_authors(self, doc):
        return [a.get("raw_author_name") for a in doc.get("authorships", []) if a.get("raw_author_name")]

    def _get_journal(self, doc):
        return (doc.get("primary_location") or {}).get("source", {}).get("host_organization_name")

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
            response = requests.get(self.cited_articles_url.format(ids="|".join(ids[i: i + 100])))
            response.raise_for_status()
            results += [
                r["doi"].removeprefix("https://doi.org/") for r in response.json().get("results", []) if r.get("doi")
            ]
        return results

    def _get_doi(self, doc):
        return (doc.get("doi") or "").removeprefix("https://doi.org/") or None

    def get_metadata(self, doi: str) -> dict:
        response = requests.get(self.url.format(doi=doi))
        if response.status_code == 404:
            return {"found": False}
        response.raise_for_status()
        doc = response.json()
        if not doc:
            return {"found": False}
        return {
            "found": True,
            "article name": doc.get("title"),
            "authors": self._get_authors(doc),
            "journal": self._get_journal(doc),
            "publish date": doc.get("publication_date"),
            "link": self._get_link(doc),
            "keywords": self._get_keywords(doc),
            "cited articles": self._get_cited_articles(doc),
            "doi": self._get_doi(doc),
            "document type": doc.get("type"),
            "open access": (doc.get("open_access") or {}).get("is_oa"),
            "status": "retracted" if doc.get("is_retracted") else "published",
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        try:
            response = requests.get(self.url.format(doi=doi), timeout=10)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            doc = response.json()
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
            print(f"OpenAlex error: {e}")
            return []


if __name__ == "__main__":
    import json

    parser = OpenAlexMetadataParser()
    metadata = parser.get_metadata("10.1128/mbio.01735-25")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
