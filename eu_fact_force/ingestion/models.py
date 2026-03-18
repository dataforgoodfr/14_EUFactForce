import logging
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import models
from django.db.models import Q
from pgvector.django import VectorField

from eu_fact_force.ingestion.s3 import save_file_to_s3

logger = logging.getLogger(__name__)
EMBEDDING_DIMENSIONS = 768


class TimeStampedModel(models.Model):
    """Abstract base model that adds created_at and updated_at to all derived models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class RawAsset(TimeStampedModel):
    """
    Abstract base for raw ingested assets (e.g. PDF, full-text).
    Concrete types: SourceFile (PDF/file). Future: RawTextAsset for abstract-only.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        STORED = "stored", "Stored"
        PARSED = "parsed", "Parsed"

    s3_key = models.CharField(max_length=512, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        abstract = True

    def delete_from_storage(self):
        """
        Remove this asset's object from S3 (or default storage).
        No-op if no s3_key; does not raise if the file is already missing.
        """
        if not self.s3_key:
            return
        try:
            if default_storage.exists(self.s3_key):
                default_storage.delete(self.s3_key)
        except Exception as e:
            logger.warning(
                "Could not delete storage file for %s %s (key=%s): %s",
                self.__class__.__name__,
                self.pk,
                self.s3_key,
                e,
            )


class SourceFile(RawAsset):
    """
    Concrete RawAsset for a stored PDF or other file (e.g. on S3).
    Canonical raw asset type for ingestion; referenced by Document, ParsedArtifact, DocumentChunk.
    """

    id = models.AutoField(primary_key=True)
    doi = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "source file"
        verbose_name_plural = "source files"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.doi or self.s3_key or self.id} ({self.status})"

    @classmethod
    def create_from_file(
        cls,
        file_path: Path,
        doi: str | None = None,
    ) -> "SourceFile":
        """Create a SourceFile from a local file path."""
        s3_key = save_file_to_s3(file_path)
        return cls.objects.create(doi=doi, s3_key=s3_key, status=cls.Status.STORED)

    def delete_source_document_from_s3(self):
        """Remove this source file from storage. Kept for backward compatibility."""
        self.delete_from_storage()


class FileMetadata(TimeStampedModel):
    """Metadata associated with an ingested file."""

    source_file = models.OneToOneField(
        "SourceFile",
        on_delete=models.CASCADE,
        related_name="metadata",
    )
    tags_pubmed = models.JSONField(
        default=list,
        blank=True,
        help_text="List of PubMed-style tags (list of strings)",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "file metadata"
        verbose_name_plural = "file metadata"

    def __str__(self):
        return f"Metadata for {self.source_file_id}"


class Document(TimeStampedModel):
    """
    Canonical record for a paper/article. Holds metadata and optional links to
    raw asset (SourceFile) and primary parsed artifact.
    """

    doi = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    title = models.CharField(max_length=1024, blank=True)
    authors_raw = models.TextField(
        blank=True,
        help_text="Authors as a single string (e.g. comma-separated).",
    )
    published_date = models.DateField(null=True, blank=True)
    source = models.CharField(
        max_length=512,
        blank=True,
        help_text="Journal or source name.",
    )
    language = models.CharField(max_length=10, blank=True)
    document_type = models.CharField(
        max_length=128,
        blank=True,
        help_text="Type/ontology label (e.g. article, report).",
    )
    external_ids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured external IDs (e.g. pmid, arxiv_id) for providers.",
    )
    raw_asset = models.ForeignKey(
        SourceFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    primary_parsed_artifact = models.OneToOneField(
        "ParsedArtifact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_as_primary",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "document"
        verbose_name_plural = "documents"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["doi"],
                condition=Q(doi__isnull=False) & ~Q(doi=""),
                name="ingestion_document_doi_unique_non_empty",
            ),
        ]
        indexes = [
            models.Index(fields=["language", "document_type"]),
            models.Index(fields=["published_date"]),
        ]

    def __str__(self):
        return self.title or self.doi or str(self.pk)


class ParsedArtifact(TimeStampedModel):
    """
    Parsed representation of a raw asset (e.g. markdown or JSON from Docling).
    Tied to a SourceFile and optionally to a canonical Document.
    """

    class Format(models.TextChoices):
        MARKDOWN = "markdown", "Markdown"
        JSON = "json", "JSON"
        HTML = "html", "HTML"

    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        related_name="parsed_artifacts",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="parsed_artifacts",
    )
    format = models.CharField(
        max_length=20,
        choices=Format.choices,
        default=Format.MARKDOWN,
    )
    storage_key = models.CharField(max_length=512)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    parser_name = models.CharField(max_length=64, blank=True)
    parser_config = models.CharField(max_length=256, blank=True)
    stats = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "parsed artifact"
        verbose_name_plural = "parsed artifacts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source_file_id} ({self.format})"


class IngestionRun(TimeStampedModel):
    """
    One ingestion attempt (DOI fetch or upload). Tracks status and optional
    link to the created Document and the raw SourceFile.
    """

    class InputType(models.TextChoices):
        DOI = "doi", "DOI"
        UPLOAD = "upload", "Upload"
        PROVIDER_SPECIFIC = "provider_specific", "Provider-specific"

    class RunStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ingestion_runs",
    )
    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ingestion_runs",
    )
    input_type = models.CharField(
        max_length=32,
        choices=InputType.choices,
        default=InputType.DOI,
    )
    input_identifier = models.CharField(max_length=512)
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    provider = models.CharField(max_length=64, blank=True)
    pipeline_version = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "ingestion run"
        verbose_name_plural = "ingestion runs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.input_type}:{self.input_identifier} ({self.status})"


class DocumentChunk(TimeStampedModel):
    """
    One chunk of a document (canonical Chunk). Linked to SourceFile for backward
    compatibility and optionally to Document and ParsedArtifact for provenance.
    """

    class ChunkType(models.TextChoices):
        TEXT = "text", "Text"
        TABLE = "table", "Table"
        FIGURE = "figure", "Figure"
        OTHER = "other", "Other"

    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chunks",
    )
    parsed_artifact = models.ForeignKey(
        ParsedArtifact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chunks",
    )
    content = models.TextField(help_text="Content of the chunk (e.g. one line)")
    order = models.PositiveIntegerField(
        default=0, help_text="Order in the original file"
    )
    chunk_type = models.CharField(
        max_length=20,
        choices=ChunkType.choices,
        default=ChunkType.TEXT,
    )
    page_number = models.PositiveIntegerField(null=True, blank=True)
    start_offset = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Character or token start offset in the source.",
    )
    end_offset = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Character or token end offset in the source.",
    )
    embedding = VectorField(
        dimensions=EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
        help_text="Dense embedding vector for semantic retrieval.",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "document chunk"
        verbose_name_plural = "document chunks"
        ordering = ["source_file", "order"]

    def __str__(self):
        return self.content[:50] + ("..." if len(self.content) > 50 else "")
