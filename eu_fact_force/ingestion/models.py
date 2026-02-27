import logging
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import models

from eu_fact_force.ingestion.s3 import save_file_to_s3

logger = logging.getLogger(__name__)


class TimeStampedModel(models.Model):
    """Abstract base model that adds created_at and updated_at to all derived models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SourceFile(TimeStampedModel):
    """A file fetched and stored (e.g. on S3), identified by doi."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        STORED = "stored", "Stored"
        PARSED = "parsed", "Parsed"

    id = models.AutoField(primary_key=True)
    doi = models.CharField(max_length=255, blank=True)
    s3_key = models.CharField(max_length=512, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

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
        """
        Remove this source file's object from S3 (or default storage).
        No-op if no s3_key; does not raise if the file is already missing.
        """
        if not self.s3_key:
            return
        try:
            if default_storage.exists(self.s3_key):
                default_storage.delete(self.s3_key)
        except Exception as e:
            logger.warning(
                "Could not delete storage file for SourceFile %s (key=%s): %s",
                self.pk,
                self.s3_key,
                e,
            )


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


class DocumentChunk(TimeStampedModel):
    """One chunk of a document (e.g. one line from CSV) linked to the source file."""

    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    content = models.TextField(help_text="Content of the chunk (e.g. one line)")
    order = models.PositiveIntegerField(
        default=0, help_text="Order in the original file"
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "document chunk"
        verbose_name_plural = "document chunks"
        ordering = ["source_file", "order"]

    def __str__(self):
        return self.content[:50] + ("..." if len(self.content) > 50 else "")
