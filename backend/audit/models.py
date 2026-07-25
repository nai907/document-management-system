from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("upload", "Upload"),
        ("view", "View"),
        ("download", "Download"),
        ("edit_metadata", "Edit metadata"),
        ("new_version", "New version"),
        ("submit_for_review", "Submit for review"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("permission_grant", "Permission grant"),
        ("permission_revoke", "Permission revoke"),
        ("move", "Move"),
        ("delete", "Delete"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_entries",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    document = models.ForeignKey(
        "documents.Document", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_entries",
    )
    target_repr = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.action} {self.target_repr} @ {self.timestamp}"


def log(actor, action, document=None, **metadata):
    """Write a single audit entry. Called explicitly from mutating views so the
    actor and metadata always reflect the real request, not a signal guess."""
    return AuditLog.objects.create(
        actor=actor if (actor and actor.is_authenticated) else None,
        action=action,
        document=document,
        target_repr=str(document) if document else metadata.get("target_repr", ""),
        metadata=metadata,
    )
