import logging
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import models
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
    document = models.ForeignKey(
        "Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_files",
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


class Document(TimeStampedModel):
    """Canonical bibliographic record for a publication."""

    _TITLE_DISPLAY_LENGTH = 80

    title = models.CharField(max_length=1024)
    doi = models.CharField(max_length=255, blank=True)
    external_ids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific identifiers, e.g. {'pmid': '123', 'arxiv': '2301.00001'}",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "document"
        verbose_name_plural = "documents"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["doi"],
                condition=models.Q(doi__gt=""),
                name="unique_document_doi_when_nonempty",
            )
        ]

    def __str__(self):
        if len(self.title) > self._TITLE_DISPLAY_LENGTH:
            return self.title[:self._TITLE_DISPLAY_LENGTH] + "..."
        return self.title


class DocumentChunk(TimeStampedModel):
    """One chunk of a document (e.g. one line from CSV) linked to the source file."""

    _CONTENT_DISPLAY_LENGTH = 50

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    content = models.TextField(help_text="Content of the chunk (e.g. one line)")
    order = models.PositiveIntegerField(
        default=0, help_text="Order in the original file"
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
        ordering = ["document", "order"]

    def __str__(self):
        content = self.content
        if len(content) > self._CONTENT_DISPLAY_LENGTH:
            return content[:self._CONTENT_DISPLAY_LENGTH] + "..."
        return content
