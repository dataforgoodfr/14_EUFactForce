from django.db import migrations
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion", "0001_initial"),
    ]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="documentchunk",
            name="embedding",
            field=VectorField(
                blank=True,
                dimensions=768,
                help_text="Dense embedding vector for semantic retrieval.",
                null=True,
            ),
        ),
    ]
