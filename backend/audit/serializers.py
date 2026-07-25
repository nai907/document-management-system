from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", default=None, read_only=True)
    document_code = serializers.CharField(source="document.code", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_username", "action", "document", "document_code",
            "target_repr", "timestamp", "metadata",
        ]
