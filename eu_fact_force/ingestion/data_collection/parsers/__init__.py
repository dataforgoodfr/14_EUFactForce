from parsers.arxiv import ArxivMetadataParser
from parsers.crossref import CrossrefMetadataParser
from parsers.hal import HALMetadataParser
from parsers.openalex import OpenAlexMetadataParser
from parsers.pubmed import PubMedMetadataParser

PARSERS = [
    CrossrefMetadataParser(),
    OpenAlexMetadataParser(),
    PubMedMetadataParser(),
    HALMetadataParser(),
    ArxivMetadataParser(),
]
