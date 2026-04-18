from django.apps import AppConfig


class IngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eu_fact_force.ingestion"
    label = "ingestion"
    verbose_name = "Ingestion (pipeline S3, parsing)"

    def ready(self):
        import sys

        import eu_fact_force.ingestion.signals  # noqa: F401

        # Pre-warm the embedding model only when running the web server,
        # not during management commands (migrate, shell, seed_db, etc.).
        if not any(cmd in sys.argv for cmd in ("migrate", "shell", "seed_db", "createsuperuser", "test")):
            import eu_fact_force.ingestion.embedding as embedding
            embedding._get_model()
