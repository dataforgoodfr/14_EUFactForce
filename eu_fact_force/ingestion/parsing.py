from eu_fact_force.ingestion.models import SourceFile


def parse_file(source_file: SourceFile) -> list[str]:
    """
    Parse the file and return a list of chunks.
    As a v0 we assume the chunks are the tags.
    """
    return source_file.metadata.tags_pubmed
