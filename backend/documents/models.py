import hashlib
import os
import re
import unicodedata

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone


class Folder(models.Model):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


def upload_to(instance, filename):
    # Transliterated to plain ASCII: some S3-compatible endpoints (observed
    # with Supabase Storage) reject PutObject for a non-ASCII key, which
    # otherwise surfaces as an unhandled 500 on upload of any file whose
    # original filename has non-ASCII characters (e.g. Thai, CJK, emoji).
    base, ext = os.path.splitext(filename)
    ascii_base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    ascii_base = re.sub(r"[^A-Za-z0-9._-]", "_", ascii_base).strip("_") or "file"
    return f"documents/{instance.document.code}/v{instance.version_number}_{ascii_base}{ext}"


class Document(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_IN_REVIEW = "in_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_IN_REVIEW, "In review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    code = models.CharField(max_length=32, unique=True, blank=True)
    title = models.CharField(max_length=255)
    normalized_title = models.CharField(max_length=255, unique=True, editable=False, blank=True)
    description = models.TextField(blank=True)
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="documents")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_documents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def save(self, *args, **kwargs):
        self.normalized_title = Document.clean_title(self.title)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.code:
            year = self.created_at.year if self.created_at else timezone.now().year
            self.code = f"DOC-{year}-{self.pk:06d}"
            super().save(update_fields=["code"])

    @property
    def latest_version(self):
        return self.versions.order_by("-version_number").first()

    @staticmethod
    def clean_title(title):
        return title.strip().lower()


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to=upload_to)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    change_note = models.CharField(max_length=500, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = [("document", "version_number")]

    def __str__(self):
        return f"{self.document.code} v{self.version_number}"

    @staticmethod
    def compute_checksum(file_obj):
        hasher = hashlib.sha256()
        for chunk in file_obj.chunks():
            hasher.update(chunk)
        return hasher.hexdigest()


class DocumentPermission(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="permissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="document_permissions",
    )
    group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.CASCADE, related_name="document_permissions"
    )
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    can_download = models.BooleanField(default=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="granted_permissions",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, group__isnull=True)
                    | models.Q(user__isnull=True, group__isnull=False)
                ),
                name="document_permission_user_xor_group",
            )
        ]

    def is_active(self):
        return self.expires_at is None or self.expires_at > timezone.now()

    def __str__(self):
        grantee = self.user or self.group
        return f"{self.document.code} -> {grantee}"
