"""Factories for test data."""

import factory
from factory.django import DjangoModelFactory

from eu_fact_force.ingestion.models import DocumentChunk, SourceFile


class SourceFileFactory(DjangoModelFactory):
    class Meta:
        model = SourceFile

    doi = ""
    s3_key = ""
    status = SourceFile.Status.STORED


class DocumentChunkFactory(DjangoModelFactory):
    class Meta:
        model = DocumentChunk

    source_file = factory.SubFactory(SourceFileFactory)
    content = ""
    order = 0
