from eu_fact_force.ingestion.data_collection.parsers.arxiv import \
    ArxivMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.crossref import \
    CrossrefMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.hal import \
    HALMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.openalex import \
    OpenAlexMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.pubmed import \
    PubMedMetadataParser
from eu_fact_force.ingestion.data_collection.parsers.unpaywall import \
    UnpaywallMetadataParser

PARSERS = [
    CrossrefMetadataParser(),
    OpenAlexMetadataParser(),
    PubMedMetadataParser(),
    HALMetadataParser(),
    ArxivMetadataParser(),
    UnpaywallMetadataParser(),
]
