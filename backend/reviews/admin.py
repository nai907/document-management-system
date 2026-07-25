from django.contrib import admin

from .models import ReviewAssignment


@admin.register(ReviewAssignment)
class ReviewAssignmentAdmin(admin.ModelAdmin):
    list_display = ("document", "version", "reviewer", "status", "assigned_at", "decided_at")
    list_filter = ("status",)
