from django.apps import AppConfig


class IngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eu_fact_force.ingestion"
    label = "ingestion"
    verbose_name = "Ingestion (pipeline S3, parsing)"
