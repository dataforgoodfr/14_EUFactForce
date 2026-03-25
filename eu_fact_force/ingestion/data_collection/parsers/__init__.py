from .arxiv import ArxivMetadataParser
from .crossref import CrossrefMetadataParser
from .hal import HALMetadataParser
from .openalex import OpenAlexMetadataParser
from .pubmed import PubMedMetadataParser

PARSERS = [
    CrossrefMetadataParser(),
    OpenAlexMetadataParser(),
    PubMedMetadataParser(),
    HALMetadataParser(),
    ArxivMetadataParser(),
]
