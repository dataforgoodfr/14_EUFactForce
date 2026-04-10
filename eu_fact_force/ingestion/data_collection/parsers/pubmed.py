import xml.etree.ElementTree as ET

import requests

from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class PubMedMetadataParser(MetadataParser):
    """Fetches metadata from the PubMed API (https://eutils.ncbi.nlm.nih.gov)."""

    def __init__(self):
        super().__init__()
        self.api_name = "pubmed"
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def _resolve_pubmed_id(self, doi: str):
        response = requests.get(
            self.search_url,
            params={"db": "pubmed", "retmode": "json", "term": doi + "[DOI]"},
        )
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None

    def _get_authors(self, article):
        names, orcids = [], []
        for author in article.findall(".//AuthorList/Author"):
            last = author.findtext("LastName") or ""
            fore = author.findtext("ForeName") or ""
            name = f"{fore} {last}".strip() or author.findtext("CollectiveName") or ""
            if name:
                names.append(name)
            orcid = next(
                (
                    aid.text.replace("http://orcid.org/", "").replace("https://orcid.org/", "")
                    for aid in author.findall("Identifier")
                    if aid.get("Source") == "ORCID" and aid.text
                ),
                None,
            )
            orcids.append(orcid)
        return names, orcids

    def _get_doi_and_pmc(self, root):
        doi, pmc_id = None, None
        for aid in root.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text
            elif aid.get("IdType") == "pmc":
                pmc_id = aid.text
        return doi, pmc_id

    def _get_cited_articles(self, root):
        cited = []
        for ref in root.findall(".//ReferenceList/Reference"):
            article_ids = {aid.get("IdType"): aid.text for aid in ref.findall("ArticleIdList/ArticleId")}
            if "doi" in article_ids:
                cited.append(article_ids["doi"])
            elif "pubmed" in article_ids:
                cited.append(f"pubmed:{article_ids['pubmed']}")
        return cited

    def _get_status(self, root):
        cc = root.find(".//CommentsCorrectionsList")
        if cc is not None:
            if cc.find("CommentsCorrections[@RefType='RetractionIn']") is not None:
                return "retracted"
            if cc.find("CommentsCorrections[@RefType='ErratumIn']") is not None:
                return "corrected"

        status = root.findtext(".//PublicationStatus")
        if status == "ppublish":
            return "published"
        return status

    def _get_pubdate(self, article):
        pubdate = article.find(".//Journal/JournalIssue/PubDate")
        if pubdate is None:
            return None
        parts = [pubdate.findtext("Year"), pubdate.findtext("Month"), pubdate.findtext("Day")]
        return " ".join(p for p in parts if p) or None

    def _get_publication_types(self, article):
        types = [pt.text for pt in article.findall(".//PublicationTypeList/PublicationType") if pt.text]
        doc_type = types[0] if types else None
        doc_subtypes = types[1:] if len(types) > 1 else None
        return doc_type, doc_subtypes

    def _get_keywords(self, root):
        keywords = [
            mh.findtext("DescriptorName")
            for mh in root.findall(".//MeshHeadingList/MeshHeading")
            if mh.findtext("DescriptorName")
        ]

        if not keywords:
            keywords = [kw.text for kw in root.findall(".//KeywordList/Keyword") if kw.text]

        return keywords or None

    def _get_response_from_pubmed_id(self, pubmed_id):
        response = requests.get(
            self.fetch_url,
            params={"db": "pubmed", "id": pubmed_id, "retmode": "xml", "rettype": "abstract"},
        )
        response.raise_for_status()
        return ET.fromstring(response.content)

    def get_metadata(self, doi: str) -> dict:
        pubmed_id = self._resolve_pubmed_id(doi)
        if not pubmed_id:
            return {"found": False}

        root = self._get_response_from_pubmed_id(pubmed_id)
        article = root.find(".//MedlineCitation/Article")
        if article is None:
            return {"found": False}

        doi_val, pmc_id = self._get_doi_and_pmc(root)
        names, orcids = self._get_authors(article)
        doc_type, doc_subtypes = self._get_publication_types(article)

        return {
            "found": True,
            "article name": article.findtext("ArticleTitle"),
            "authors": {
                "name": names,
                "orcid": orcids,
            },
            "journal": article.findtext(".//Journal/Title"),
            "publish date": self._get_pubdate(article),
            "link": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/" if pmc_id else None,
            "abstract": article.findtext("Abstract/AbstractText"),
            "keywords": self._get_keywords(root),
            "cited articles": self._get_cited_articles(root),
            "doi": doi_val,
            "document type": doc_type,
            "document subtypes": doc_subtypes,
            "open access": pmc_id is not None,
            "language": article.findtext("Language"),
            "status": self._get_status(root),
            "cited by count": None,
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        return []


if __name__ == "__main__":
    import json

    parser = PubMedMetadataParser()
    metadata = parser.get_metadata("10.1177/2515690X20967323")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
