"""
This module allows for a simple exploration of the database directly through the browser.
See the pages on <url>/admin
"""

from django.contrib import admin

from .models import Document, DocumentChunk, FileMetadata, IngestionRun, ParsedArtifact, SourceFile


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("id", "doi", "s3_key", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("doi",)


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ("source_file", "tags_pubmed", "created_at")
    raw_id_fields = ("source_file",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "doi", "language", "document_type", "published_date", "created_at")
    list_filter = ("language", "document_type")
    search_fields = ("title", "doi", "authors_raw")
    raw_id_fields = ("raw_asset", "primary_parsed_artifact")


@admin.register(ParsedArtifact)
class ParsedArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "source_file", "document", "format", "page_count", "parser_name", "created_at")
    list_filter = ("format",)
    raw_id_fields = ("source_file", "document")


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ("id", "input_type", "input_identifier", "status", "provider", "document", "created_at")
    list_filter = ("input_type", "status", "provider")
    search_fields = ("input_identifier",)
    raw_id_fields = ("document", "source_file")


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "source_file", "document", "order", "chunk_type", "page_number", "content_preview", "created_at")
    list_filter = ("source_file", "chunk_type")
    raw_id_fields = ("source_file", "document", "parsed_artifact")
    ordering = ("source_file", "order")

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:80] + ("..." if len(obj.content) > 80 else "")
