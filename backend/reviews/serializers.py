from rest_framework import serializers

from .models import ReviewAssignment


class ReviewAssignmentSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True)
    document_code = serializers.CharField(source="document.code", read_only=True)
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = ReviewAssignment
        fields = [
            "id", "document", "document_code", "document_title", "version",
            "reviewer", "reviewer_username", "status", "assigned_by",
            "assigned_at", "decided_at", "comment",
        ]
        read_only_fields = [
            "document", "version", "assigned_by", "status", "assigned_at", "decided_at",
        ]
