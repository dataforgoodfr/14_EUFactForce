import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingestion", "0002_documentchunk_embedding"),
    ]

    operations = [
        # Remove FileMetadata (superseded by IngestionRun + ParsedArtifact)
        migrations.DeleteModel(
            name="FileMetadata",
        ),
        # Introduce Document as the canonical bibliographic record
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=1024)),
                ("doi", models.CharField(blank=True, max_length=255)),
                (
                    "external_ids",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Provider-specific identifiers, e.g. {'pmid': '123', 'arxiv': '2301.00001'}",
                    ),
                ),
            ],
            options={
                "verbose_name": "document",
                "verbose_name_plural": "documents",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.UniqueConstraint(
                condition=models.Q(doi__gt=""),
                fields=["doi"],
                name="unique_document_doi_when_nonempty",
            ),
        ),
        # Add optional FK from SourceFile to Document (set when parsed)
        migrations.AddField(
            model_name="sourcefile",
            name="document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_files",
                to="ingestion.document",
            ),
        ),
        # Add required FK from DocumentChunk to Document
        migrations.AddField(
            model_name="documentchunk",
            name="document",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chunks",
                to="ingestion.document",
            ),
        ),
        # Remove direct SourceFile FK from DocumentChunk; navigate via document instead
        migrations.RemoveField(
            model_name="documentchunk",
            name="source_file",
        ),
    ]
