from abc import ABC, abstractmethod
import requests


class MetadataParser(ABC):
    def __init__(self):
        self.fields_mapping = {
            "article name":  "",
            "authors":       "",
            "journal":       "",
            "publish date":  "",
            "link":          "",
            "keywords":      "",
            "cited articles": "",
            "doi":           "",
            "article type":  "",
            "open access":   "",
            "status":        ""
        }

        self.fields_mapping = {}

    @abstractmethod
    def get_metadata(self, doi: str) -> dict:
        pass

    def download_pdf(self, pdf_url, save_path):
        response = requests.get(pdf_url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"PDF downloaded successfully to {save_path}")
        else:
            print(f"Failed to download PDF. Status code: {response.status_code}")


class HALMetadataParser(MetadataParser):
    def __init__(self):
        super().__init__()
        self.url = "https://api.archives-ouvertes.fr/search/?q=doiId_s:{doi}&fl=*"

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
            "found":          True,
            "article name":   doc.get("title_s"),
            "authors":        doc.get("authFullName_s"),
            "journal":        doc.get("journalTitle_s"),
            "publish date":   doc.get("publicationDate_s"),
            "link":           doc.get("uri_s"),
            "keywords":       self._get_keywords(doc),
            "cited articles": None,
            "doi":            doc.get("doiId_s"),
            "article type":   doc.get("docType_s"),
            "open access":    doc.get("openAccess_bool"),
            "status":         None,
        }
    


if __name__ == "__main__":
    parser = HALMetadataParser()
    doi = "10.26855/ijcemr.2021.01.001"
    metadata = parser.get_metadata(doi)
    print(metadata)