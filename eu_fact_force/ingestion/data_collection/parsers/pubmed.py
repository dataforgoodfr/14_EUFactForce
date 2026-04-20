import xml.etree.ElementTree as ET

import requests
from eu_fact_force.ingestion.data_collection.parsers.base import MetadataParser


class PubMedMetadataParser(MetadataParser):
    """Fetches metadata from the PubMed API (https://eutils.ncbi.nlm.nih.gov)."""

    def __init__(self):
        super().__init__()
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        self.session = requests.Session()
        self._cache = {}
        self.pmcid = None

    def _get_response(self, doi: str):
        if doi not in self._cache:
            search = self.session.get(
                self.search_url,
                params={"db": "pubmed", "retmode": "json", "term": doi + "[DOI]"},
                timeout=10,
            )
            search.raise_for_status()
            ids = search.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                self._cache[doi] = None
            else:
                response = self.session.get(
                    self.fetch_url,
                    params={"db": "pubmed", "id": ids[0], "retmode": "xml", "rettype": "abstract"},
                    timeout=10,
                )
                response.raise_for_status()
                self._cache[doi] = ET.fromstring(response.content)
        return self._cache[doi]

    def _get_authors(self, article):
        authors = []
        for author in article.findall(".//AuthorList/Author"):
            last = author.findtext("LastName") or ""
            fore = author.findtext("ForeName") or ""
            name = f"{fore} {last}".strip() or author.findtext("CollectiveName") or ""
            if not name:
                continue
            orcid = next(
                (
                    aid.text.replace("http://orcid.org/", "").replace("https://orcid.org/", "")
                    for aid in author.findall("Identifier")
                    if aid.get("Source") == "ORCID" and aid.text
                ),
                None,
            )
            authors.append({"name": name, "orcid": orcid})
        return authors

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

    def _get_abstract(self, article):
        parts = []
        for at in article.findall("Abstract/AbstractText"):
            text = "".join(at.itertext()).strip()
            if not text:
                continue
            label = at.get("Label")
            parts.append(f"{label}: {text}" if label else text)
        return " ".join(parts) or None

    def _get_keywords(self, root):
        keywords = [
            mh.findtext("DescriptorName")
            for mh in root.findall(".//MeshHeadingList/MeshHeading")
            if mh.findtext("DescriptorName")
        ]

        if not keywords:
            keywords = [kw.text for kw in root.findall(".//KeywordList/Keyword") if kw.text]

        return keywords or None

    def get_metadata(self, doi: str) -> dict:
        root = self._get_response(doi)
        if root is None:
            return {"found": False}
        article = root.find(".//MedlineCitation/Article")
        if article is None:
            return {"found": False}

        doi_val, self.pmcid = self._get_doi_and_pmc(root)
        doc_type, doc_subtypes = self._get_publication_types(article)

        article_name = article.findtext("ArticleTitle")
        if not article_name:
            return {"found": False}

        return {
            "found": True,
            "title": article_name,
            "authors": self._get_authors(article),
            "journal": {
                "name": article.findtext(".//Journal/Title"),
                "issn": article.findtext(".//Journal/ISSN"),
            },
            "publication date": self._get_pubdate(article),
            "status": self._get_status(root),
            "doi": doi_val,
            "link": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{self.pmcid}/" if self.pmcid else None,
            "document type": doc_type,
            "document subtypes": doc_subtypes,
            "open access": self.pmcid is not None,
            "language": article.findtext("Language"),
            "cited by count": None,
            "abstract": self._get_abstract(article),
            "keywords": self._get_keywords(root),
            "cited articles": self._get_cited_articles(root),
        }

    def get_pdf_url(self, doi: str) -> list[str]:
        doi_str = doi.replace("/", "_")
        pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{self.pmcid}/pdf/{doi_str}.pdf"

        return [pdf_url] if self.pmcid else []
