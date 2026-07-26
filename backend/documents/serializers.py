from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import serializers

from reviews.serializers import ReviewAssignmentSerializer

from .models import (
    Document,
    DocumentPermission,
    DocumentVersion,
    Folder,
    Tag,
)
from .validators import get_duplicate_title_error, get_file_type_error

User = get_user_model()


class FolderSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(source="documents.count", read_only=True)

    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "created_by", "created_at", "document_count"]
        read_only_fields = ["created_by", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = DocumentVersion
        # Deliberately excludes `file`: DRF would serialize it as a direct
        # (for S3, presigned-but-still-bypassing) URL to anyone who can view
        # the document, regardless of their `can_download` grant. Downloads
        # only ever go through DocumentDownloadView, which checks permission
        # first and streams the bytes itself.
        fields = [
            "id", "document", "version_number", "uploaded_by",
            "uploaded_by_username", "uploaded_at", "change_note", "size", "checksum",
        ]
        read_only_fields = ["document", "version_number", "uploaded_by", "size", "checksum"]


class DocumentPermissionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True, default=None)
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)
    granted_by_username = serializers.CharField(source="granted_by.username", read_only=True, default=None)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = DocumentPermission
        fields = [
            "id", "document", "user", "user_username", "group", "group_name",
            "can_view", "can_edit", "can_approve", "can_download",
            "granted_by", "granted_by_username", "granted_at", "expires_at", "is_active",
        ]
        read_only_fields = ["document", "granted_by", "granted_at"]

    def get_is_active(self, obj):
        return obj.is_active()

    def validate(self, attrs):
        user = attrs.get("user")
        group = attrs.get("group")
        if bool(user) == bool(group):
            raise serializers.ValidationError(
                "Exactly one of `user` or `group` must be set."
            )
        return attrs


class DocumentListSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True, default=None)
    tags = TagSerializer(many=True, read_only=True)
    latest_version_number = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "code", "title", "description", "folder", "folder_name", "tags",
            "owner", "owner_username", "status",
            "created_at", "updated_at", "latest_version_number",
        ]
        read_only_fields = ["code", "owner", "status", "created_at", "updated_at"]

    def get_latest_version_number(self, obj):
        latest = obj.latest_version
        return latest.version_number if latest else None

    def validate_title(self, value):
        exclude_pk = self.instance.pk if self.instance else None
        error = get_duplicate_title_error(value, exclude_pk=exclude_pk)
        if error:
            raise serializers.ValidationError(error)
        return value


class DocumentDetailSerializer(DocumentListSerializer):
    versions = DocumentVersionSerializer(many=True, read_only=True)
    permissions = DocumentPermissionSerializer(many=True, read_only=True)
    review_assignments = serializers.SerializerMethodField()

    class Meta(DocumentListSerializer.Meta):
        fields = DocumentListSerializer.Meta.fields + ["versions", "permissions", "review_assignments"]

    def get_review_assignments(self, obj):
        latest = obj.latest_version
        if not latest:
            return []
        qs = obj.review_assignments.filter(version=latest).select_related("reviewer")
        # Pending reviewers first (the ones actually holding things up), then
        # decided ones, each group ordered by when they were assigned.
        assignments = sorted(qs, key=lambda a: (a.status != "pending", a.assigned_at))
        return ReviewAssignmentSerializer(assignments, many=True).data


class DocumentCreateSerializer(serializers.ModelSerializer):
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, write_only=True
    )
    file = serializers.FileField(write_only=True)
    change_note = serializers.CharField(max_length=500, required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "title", "description", "folder", "tag_names",
            "file", "change_note",
        ]

    def validate_title(self, value):
        error = get_duplicate_title_error(value)
        if error:
            raise serializers.ValidationError(error)
        return value

    def validate_file(self, value):
        error = get_file_type_error(value)
        if error:
            raise serializers.ValidationError(error)
        return value

    def create(self, validated_data):
        tag_names = validated_data.pop("tag_names", [])
        file_obj = validated_data.pop("file")
        change_note = validated_data.pop("change_note", "")
        request = self.context["request"]

        checksum = DocumentVersion.compute_checksum(file_obj)
        file_obj.seek(0)

        # Atomic so a storage failure while saving the version's file (e.g.
        # the S3 backend rejecting the upload) rolls back the Document row
        # too, instead of leaving an orphaned draft with no version.
        with transaction.atomic():
            document = Document.objects.create(owner=request.user, **validated_data)
            if tag_names:
                tags = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
                document.tags.set(tags)

            DocumentVersion.objects.create(
                document=document,
                version_number=1,
                file=file_obj,
                uploaded_by=request.user,
                change_note=change_note,
                size=file_obj.size,
                checksum=checksum,
            )
        return document
