import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingestion", "0003_document_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParsedArtifact",
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
                (
                    "document",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parsed_artifact",
                        to="ingestion.document",
                    ),
                ),
                (
                    "docling_output",
                    models.JSONField(
                        help_text="Raw Docling JSON output.",
                    ),
                ),
                (
                    "postprocessed_text",
                    models.TextField(
                        help_text="Text after postprocessing pipeline.",
                    ),
                ),
                (
                    "metadata_extracted",
                    models.JSONField(
                        help_text="Snapshot of parser-extracted metadata, used for audit and reconciliation.",
                    ),
                ),
                (
                    "parser_config",
                    models.JSONField(
                        help_text="Docling parameters and model versions used during parsing.",
                    ),
                ),
            ],
            options={
                "verbose_name": "parsed artifact",
                "verbose_name_plural": "parsed artifacts",
                "app_label": "ingestion",
            },
        ),
    ]
