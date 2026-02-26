from django.db import models


class SourceFile(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "source file"
        verbose_name_plural = "source files"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.doi or self.s3_key or self.id} ({self.status})"


class FileMetadata(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "file metadata"
        verbose_name_plural = "file metadata"

    def __str__(self):
        return f"Metadata for {self.source_file_id}"


class DocumentChunk(models.Model):
    """One chunk of a document (e.g. one line from CSV) linked to the source file."""

    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    content = models.TextField(
        help_text="Content of the chunk (e.g. one line)"
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Order in the original file"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ingestion"
        verbose_name = "document chunk"
        verbose_name_plural = "document chunks"
        ordering = ["source_file", "order"]

    def __str__(self):
        return self.content[:50] + ("..." if len(self.content) > 50 else "")
