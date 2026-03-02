"""
Signal handlers for the ingestion app.
"""

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import SourceFile


@receiver(pre_delete, sender=SourceFile)
def delete_source_document_from_s3(sender, instance, **kwargs):
    """When a SourceFile is deleted, remove its file from storage (S3)."""
    instance.delete_source_document_from_s3()
