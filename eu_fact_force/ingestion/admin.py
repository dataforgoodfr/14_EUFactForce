"""
This module allows for a simple exploration of the database directly through the browser.
See the pages on <url>/admin
"""

from django.contrib import admin

from .models import FileMetadata, ParsedElement, SourceFile


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("id", "file_id", "doi", "filename", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("file_id", "filename")


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ("source_file", "tags_pubmed", "created_at")
    raw_id_fields = ("source_file",)


@admin.register(ParsedElement)
class ParsedElementAdmin(admin.ModelAdmin):
    list_display = ("id", "source_file", "order", "content_preview", "created_at")
    list_filter = ("source_file",)
    raw_id_fields = ("source_file",)
    ordering = ("source_file", "order")

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:80] + ("..." if len(obj.content) > 80 else "")
        return obj.content[:80] + ("..." if len(obj.content) > 80 else "")
