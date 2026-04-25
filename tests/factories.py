"""Factories for test data."""

import random

import factory
from factory.django import DjangoModelFactory

from eu_fact_force.ingestion.models import (
    EMBEDDING_DIMENSIONS,
    Author,
    Document,
    DocumentChunk,
    IngestionRun,
    ParsedArtifact,
    SourceFile,
)


class SourceFileFactory(DjangoModelFactory):
    class Meta:
        model = SourceFile

    doi = ""
    s3_key = ""
    status = SourceFile.Status.STORED


class AuthorFactory(DjangoModelFactory):
    class Meta:
        model = Author

    full_name = factory.Sequence(lambda n: f"Author {n}")
    orcid = None


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Sequence(lambda n: f"Document {n}")
    doi = ""
    external_ids = factory.LazyFunction(dict)


class ParsedArtifactFactory(DjangoModelFactory):
    class Meta:
        model = ParsedArtifact

    document = factory.SubFactory(DocumentFactory)
    docling_output = factory.LazyFunction(dict)
    postprocessed_text = factory.Sequence(lambda n: f"Postprocessed text {n}")
    metadata_extracted = factory.LazyFunction(dict)
    parser_config = factory.LazyFunction(dict)


class IngestionRunFactory(DjangoModelFactory):
    class Meta:
        model = IngestionRun

    document = factory.SubFactory(DocumentFactory)
    source_file = None
    status = IngestionRun.Status.RUNNING
    stage = IngestionRun.Stage.ACQUIRE
    success_kind = None
    input_type = IngestionRun.InputType.DOI
    input_identifier = factory.Sequence(lambda n: f"10.1234/run{n}")
    provider = None
    raw_provider_payload = None
    error_message = None
    error_stage = None
    pipeline_version = "0.1.0"


def _random_embedding_vector() -> list[float]:
    return [random.random() for _ in range(EMBEDDING_DIMENSIONS)]


class DocumentChunkFactory(DjangoModelFactory):
    class Meta:
        model = DocumentChunk

    document = factory.SubFactory(DocumentFactory)
    order = factory.Sequence(lambda n: n)
    content = factory.Sequence(lambda n: f"Paragraphe {n + 1}")
    embedding = factory.LazyFunction(_random_embedding_vector)
