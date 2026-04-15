"""Tests for ingestion models: constraints, cascade behaviour, and relationships."""

from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import IntegrityError

from eu_fact_force.ingestion.models import Document, DocumentChunk, IngestionRun, ParsedArtifact, SourceFile
from tests.factories import DocumentChunkFactory, DocumentFactory, IngestionRunFactory, ParsedArtifactFactory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"


class TestSourceFile:
    @pytest.mark.django_db
    def test_deleting_source_file_removes_file_from_storage(self, tmp_path, tmp_storage):
        """
        When a SourceFile is deleted, the corresponding file is removed from storage.
        save_file_to_s3 uses get_s3_client(); on mock we write to tmp_storage so that
        default_storage (overridden to tmp_storage) and the client target the same place.
        """
        fn = tmp_path / "test_file.txt"
        with fn.open("w") as f:
            f.write("test content")

        def fake_upload_fileobj(Fileobj, Bucket, Key):
            dest = tmp_storage / Key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(Fileobj.read())

        with patch("eu_fact_force.ingestion.s3.get_s3_client") as mock_client:
            mock_client.return_value.upload_fileobj = fake_upload_fileobj
            inp = SourceFile.create_from_file(fn, doi="test_doi")

        s3_fn = tmp_storage / inp.s3_key
        assert s3_fn.exists()
        inp.delete()
        assert not s3_fn.exists()


class TestDocumentTitle:
    @pytest.mark.django_db
    def test_document_requires_title(self):
        """Document.title is non-null and non-blank at the DB level."""
        with pytest.raises(IntegrityError):
            Document.objects.create(title=None)

    @pytest.mark.django_db
    def test_document_created_with_title(self):
        """A Document with a valid title is persisted."""
        doc = Document.objects.create(title="Climate change and health")
        assert doc.pk is not None
        assert doc.title == "Climate change and health"


class TestDocumentDOI:
    @pytest.mark.django_db
    def test_duplicate_nonempty_doi_rejected(self):
        """Two Documents with the same non-empty DOI raise IntegrityError."""
        Document.objects.create(title="Paper A", doi="10.1234/abc")
        with pytest.raises(IntegrityError):
            Document.objects.create(title="Paper B", doi="10.1234/abc")

    @pytest.mark.django_db
    def test_multiple_documents_without_doi_allowed(self):
        """Multiple Documents with empty DOI are allowed (partial unique constraint)."""
        Document.objects.create(title="Report A", doi="")
        Document.objects.create(title="Report B", doi="")
        assert Document.objects.filter(doi="").count() == 2

    @pytest.mark.django_db
    def test_doi_none_raises_integrity_error(self):
        """doi=None is NOT equivalent to doi="" — it violates the NOT NULL constraint."""
        with pytest.raises(IntegrityError):
            Document.objects.create(title="Report C", doi=None)


class TestDocumentSourceFile:
    @pytest.mark.django_db
    def test_document_created_without_source_file(self):
        """A Document can exist without a linked SourceFile (metadata-only state)."""
        doc = Document.objects.create(title="Metadata-only paper", doi="10.9999/meta")
        assert doc.pk is not None
        assert doc.source_file is None

    @pytest.mark.django_db
    def test_deleting_source_file_cascades_to_document(self):
        """Deleting a SourceFile deletes the linked Document via CASCADE."""
        sf = SourceFile.objects.create(doi="10.1111/cascade", status=SourceFile.Status.STORED)
        doc = Document.objects.create(title="Cascade paper", source_file=sf)
        doc_pk = doc.pk

        sf.delete()

        assert not Document.objects.filter(pk=doc_pk).exists()

    @pytest.mark.django_db
    def test_document_cannot_link_to_more_than_one_source_file(self):
        """A SourceFile can be linked to at most one Document (OneToOneField constraint)."""
        from django.db import IntegrityError

        sf = SourceFile.objects.create(doi="10.2222/unique", status=SourceFile.Status.STORED)
        Document.objects.create(title="First paper", source_file=sf)

        with pytest.raises(IntegrityError):
            Document.objects.create(title="Second paper", source_file=sf)


class TestParsedArtifact:
    @pytest.mark.django_db
    def test_parsed_artifact_fields_writable_and_retrievable(self):
        """All four ParsedArtifact fields can be written and retrieved."""
        doc = DocumentFactory()
        artifact = ParsedArtifact.objects.create(
            document=doc,
            docling_output={"pages": 10, "tables": []},
            postprocessed_text="Clean text content.",
            metadata_extracted={"title": "My Paper", "authors": ["Alice"]},
            parser_config={"model": "docling-v2", "ocr": True},
        )
        fetched = ParsedArtifact.objects.get(pk=artifact.pk)
        assert fetched.docling_output == {"pages": 10, "tables": []}
        assert fetched.postprocessed_text == "Clean text content."
        assert fetched.metadata_extracted == {"title": "My Paper", "authors": ["Alice"]}
        assert fetched.parser_config == {"model": "docling-v2", "ocr": True}

    @pytest.mark.django_db
    def test_second_parsed_artifact_for_same_document_raises_integrity_error(self):
        """OneToOneField enforces at most one ParsedArtifact per Document."""
        artifact = ParsedArtifactFactory()
        with pytest.raises(IntegrityError):
            ParsedArtifact.objects.create(
                document=artifact.document,
                docling_output={},
                postprocessed_text="",
                metadata_extracted={},
                parser_config={},
            )

    @pytest.mark.django_db
    def test_parsed_artifact_accessible_via_document(self):
        """Document.parsed_artifact reverse accessor returns the linked artifact."""
        artifact = ParsedArtifactFactory()
        assert artifact.document.parsed_artifact == artifact


class TestIngestionRun:
    @pytest.mark.django_db
    def test_success_metadata_only(self):
        """A run can transition to success with success_kind=metadata_only and stage=done."""
        run = IngestionRunFactory(status=IngestionRun.Status.RUNNING, stage=IngestionRun.Stage.ACQUIRE)
        run.status = IngestionRun.Status.SUCCESS
        run.success_kind = IngestionRun.SuccessKind.METADATA_ONLY
        run.stage = IngestionRun.Stage.DONE
        run.save()

        fetched = IngestionRun.objects.get(pk=run.pk)
        assert fetched.status == IngestionRun.Status.SUCCESS
        assert fetched.success_kind == IngestionRun.SuccessKind.METADATA_ONLY
        assert fetched.stage == IngestionRun.Stage.DONE

    @pytest.mark.django_db
    def test_success_full(self):
        """A run can transition to success with success_kind=full and stage=done."""
        run = IngestionRunFactory(status=IngestionRun.Status.RUNNING, stage=IngestionRun.Stage.ACQUIRE)
        run.status = IngestionRun.Status.SUCCESS
        run.success_kind = IngestionRun.SuccessKind.FULL
        run.stage = IngestionRun.Stage.DONE
        run.save()

        fetched = IngestionRun.objects.get(pk=run.pk)
        assert fetched.status == IngestionRun.Status.SUCCESS
        assert fetched.success_kind == IngestionRun.SuccessKind.FULL
        assert fetched.stage == IngestionRun.Stage.DONE

    @pytest.mark.django_db
    def test_failed_run_records_error_fields(self):
        """A failed run records error_message and error_stage."""
        run = IngestionRunFactory(status=IngestionRun.Status.RUNNING, stage=IngestionRun.Stage.ACQUIRE)
        run.status = IngestionRun.Status.FAILED
        run.error_message = "Metadata provider returned 404"
        run.error_stage = IngestionRun.Stage.ACQUIRE
        run.save()

        fetched = IngestionRun.objects.get(pk=run.pk)
        assert fetched.status == IngestionRun.Status.FAILED
        assert fetched.error_message == "Metadata provider returned 404"
        assert fetched.error_stage == IngestionRun.Stage.ACQUIRE

    @pytest.mark.django_db
    def test_duplicate_doi_rejected_before_ingestion_run_created(self):
        """A duplicate non-empty DOI raises ValueError before any IngestionRun row is created."""
        doi = "10.9999/duplicate"
        existing_doc = Document.objects.create(title="Existing paper", doi=doi)
        new_doc = Document.objects.create(title="New paper attempt", doi="")

        count_before = IngestionRun.objects.count()
        with pytest.raises(ValueError, match=doi):
            IngestionRun.start(
                document=new_doc,
                input_type=IngestionRun.InputType.DOI,
                input_identifier=doi,
                pipeline_version="0.1.0",
            )

        assert IngestionRun.objects.count() == count_before
        existing_doc  # silence unused-variable warning


class TestDocumentChunk:
    @pytest.mark.django_db
    def test_document_chunk_requires_document(self):
        """DocumentChunk cannot be created without a Document FK."""
        with pytest.raises(IntegrityError):
            DocumentChunk.objects.create(
                document=None,
                content="Some text",
                order=1,
            )

    @pytest.mark.django_db
    def test_document_chunk_linked_to_document(self):
        """DocumentChunk is accessible via Document.chunks."""
        chunk = DocumentChunkFactory()
        assert chunk.document is not None
        assert chunk in chunk.document.chunks.all()
