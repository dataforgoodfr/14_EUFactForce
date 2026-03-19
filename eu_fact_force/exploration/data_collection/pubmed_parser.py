from metadata_parser import MetadataParser
import requests


class PubMedMetadataParser(MetadataParser):
    def __init__(self):
        super().__init__()
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def _resolve_pubmed_id(self, doi: str):
        response = requests.get(self.search_url, params={
            "db": "pubmed",
            "retmode": "json",
            "term": doi + "[DOI]",
        })
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None

    def _get_authors(self, doc):
        return [a.get("name") for a in doc.get("authors", []) if a.get("name")]

    def _get_doi(self, doc):
        for item in doc.get("articleids", []):
            if item.get("idtype") == "doi":
                return item.get("value")
        return None

    def _get_article_type(self, doc):
        pubtypes = doc.get("pubtype", [])
        return pubtypes[0] if pubtypes else None

    def _get_status(self, doc):
        return "retracted" if "Retracted Publication" in doc.get("pubtype", []) else "published"

    def get_metadata(self, doi: str) -> dict:
        pubmed_id = self._resolve_pubmed_id(doi)
        if not pubmed_id:
            return {"found": False}

        response = requests.get(self.summary_url, params={
            "db": "pubmed",
            "id": pubmed_id,
            "retmode": "json",
        })
        response.raise_for_status()
        doc = response.json().get("result", {}).get(pubmed_id)

        if not doc:
            return {"found": False}

        return {
            "found":           True,
            "article name":    doc.get("title"),
            "authors":         self._get_authors(doc),
            "journal":         doc.get("fulljournalname"),
            "publish date":    doc.get("pubdate"),
            "link":            None,
            "keywords":        None,
            "cited articles":  None,
            "doi":             self._get_doi(doc),
            "article type":    self._get_article_type(doc),
            "open access":     None,
            "status":          self._get_status(doc),
        }


if __name__ == "__main__":
    parser = PubMedMetadataParser()
    doi = "10.1016/S0140-6736(97)11096-0"
    metadata = parser.get_metadata(doi)
    print(metadata)
