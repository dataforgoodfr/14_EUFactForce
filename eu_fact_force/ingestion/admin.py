"""
This module allows for a simple exploration of the database directly through the browser.
See the pages on <url>/admin
"""

from django.contrib import admin

from .models import Document, DocumentChunk, IngestionRun, ParsedArtifact, SourceFile


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("id", "doi", "s3_key", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("doi",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "doi", "source_file", "created_at")
    search_fields = ("title", "doi")
    raw_id_fields = ("source_file",)


@admin.register(ParsedArtifact)
class ParsedArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "created_at")
    raw_id_fields = ("document",)


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "input_type",
        "input_identifier",
        "status",
        "stage",
        "success_kind",
        "pipeline_version",
        "created_at",
    )
    list_filter = ("status", "stage", "input_type", "success_kind")
    search_fields = ("input_identifier", "provider", "error_message")
    raw_id_fields = ("document", "source_file")


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    _CONTENT_PREVIEW_LENGTH = 80

    list_display = ("id", "document", "order", "content_preview", "created_at")
    list_filter = ("document",)
    raw_id_fields = ("document",)
    ordering = ("document", "order")

    @admin.display(description="Content")
    def content_preview(self, obj):
        content = obj.content
        if len(content) > self._CONTENT_PREVIEW_LENGTH:
            return content[:self._CONTENT_PREVIEW_LENGTH] + "..."
        return content
