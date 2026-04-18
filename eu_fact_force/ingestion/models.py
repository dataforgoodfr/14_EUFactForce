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


class Author(models.Model):
    """A person who authored a document."""

    full_name = models.CharField(max_length=512)
    orcid = models.CharField(
        max_length=19,
        null=True,
        blank=True,
        unique=True,
        help_text="ORCID identifier (e.g. 0000-0001-2345-6789). Unique when set.",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "author"
        verbose_name_plural = "authors"

    def __str__(self):
        return self.full_name

    @classmethod
    def from_list(cls, entries: list[dict]) -> list["Author"]:
        """
        Create or retrieve Author instances from a list of {name, orcid} dicts.
        Returns the list of Author instances in the same order.
        """
        authors = []
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            orcid = entry.get("orcid") or None
            if orcid:
                author, _ = cls.objects.get_or_create(orcid=orcid, defaults={"full_name": entry["name"]})
            else:
                author = cls.objects.filter(full_name=entry["name"]).first()
                if author is None:
                    author = cls.objects.create(full_name=entry["name"])
            authors.append(author)
        return authors


class Document(TimeStampedModel):
    """Canonical bibliographic record for a publication."""

    _TITLE_DISPLAY_LENGTH = 80

    title = models.CharField(max_length=1024)
    doi = models.CharField(max_length=255, blank=True)
    source_file = models.OneToOneField(
        "SourceFile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="document",
    )
    external_ids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific identifiers, e.g. {'pmid': '123', 'arxiv': '2301.00001'}",
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="List of keywords associated with the document.",
    )
    authors = models.ManyToManyField(
        Author,
        blank=True,
        related_name="documents",
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


class IngestionRun(TimeStampedModel):
    """Records every ingestion attempt with full stage and outcome tracking."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        ACQUIRE = "acquire", "Acquire"
        STORE = "store", "Store"
        PARSE = "parse", "Parse"
        CHUNK = "chunk", "Chunk"
        DONE = "done", "Done"

    class SuccessKind(models.TextChoices):
        METADATA_ONLY = "metadata_only", "Metadata Only"
        FULL = "full", "Full"

    class InputType(models.TextChoices):
        DOI = "doi", "DOI"
        PDF_UPLOAD = "pdf_upload", "PDF Upload"

    document = models.ForeignKey(
        "Document",
        on_delete=models.CASCADE,
        related_name="ingestion_runs",
    )
    source_file = models.ForeignKey(
        "SourceFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.ACQUIRE,
    )
    success_kind = models.CharField(
        max_length=20,
        choices=SuccessKind.choices,
        null=True,
        blank=True,
    )
    input_type = models.CharField(
        max_length=20,
        choices=InputType.choices,
    )
    input_identifier = models.CharField(
        max_length=512,
        help_text="DOI string or upload reference",
    )
    provider = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Metadata API used",
    )
    raw_provider_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Verbatim API response from the metadata provider",
    )
    error_message = models.TextField(null=True, blank=True)
    error_stage = models.CharField(max_length=20, null=True, blank=True)
    pipeline_version = models.CharField(max_length=64)

    class Meta:
        app_label = "ingestion"
        verbose_name = "ingestion run"
        verbose_name_plural = "ingestion runs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"IngestionRun({self.input_identifier}, {self.status}, stage={self.stage})"

    @classmethod
    def start(
        cls,
        *,
        document: "Document",
        input_type: str,
        input_identifier: str,
        pipeline_version: str,
        source_file: "SourceFile | None" = None,
    ) -> "IngestionRun":
        """
        Create a new IngestionRun at the very start of ingestion.

        Raises ValueError if input_identifier is a non-empty DOI that already
        exists on another Document, so no IngestionRun row is ever created for
        a duplicate DOI.
        """
        if input_type == cls.InputType.DOI and input_identifier:
            if Document.objects.filter(doi=input_identifier).exclude(pk=document.pk).exists():
                raise ValueError(
                    f"A Document with DOI '{input_identifier}' already exists."
                )
        return cls.objects.create(
            document=document,
            source_file=source_file,
            input_type=input_type,
            input_identifier=input_identifier,
            pipeline_version=pipeline_version,
        )


class ParsedArtifact(TimeStampedModel):
    """Single parse output for a Document (one per Document, enforced at DB level)."""

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="parsed_artifact",
    )
    docling_output = models.JSONField(
        help_text="Raw Docling JSON output.",
    )
    postprocessed_text = models.TextField(
        help_text="Text after postprocessing pipeline.",
    )
    metadata_extracted = models.JSONField(
        help_text="Snapshot of parser-extracted metadata, used for audit and reconciliation.",
    )
    parser_config = models.JSONField(
        help_text="Docling parameters and model versions used during parsing.",
    )

    class Meta:
        app_label = "ingestion"
        verbose_name = "parsed artifact"
        verbose_name_plural = "parsed artifacts"

    def __str__(self):
        return f"ParsedArtifact for {self.document}"


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
