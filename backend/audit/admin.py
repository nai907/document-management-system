from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "document", "target_repr")
    list_filter = ("action",)
    search_fields = ("target_repr", "actor__username")
    date_hierarchy = "timestamp"
