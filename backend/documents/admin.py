from django.contrib import admin

from .models import Document, DocumentPermission, DocumentVersion, Folder, Tag


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "created_by", "created_at")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ("uploaded_at", "size", "checksum")


class DocumentPermissionInline(admin.TabularInline):
    model = DocumentPermission
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "owner", "status", "folder", "updated_at")
    list_filter = ("status",)
    search_fields = ("code", "title", "description")
    inlines = [DocumentVersionInline, DocumentPermissionInline]
