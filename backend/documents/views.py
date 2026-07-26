from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.models import log as audit_log
from audit.serializers import AuditLogSerializer
from reviews.models import ReviewAssignment

from .models import Document, DocumentPermission, DocumentVersion, Folder
from .permissions import HasDocumentPermission, visible_documents_for
from .serializers import (
    DocumentCreateSerializer,
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentPermissionSerializer,
    DocumentVersionSerializer,
    FolderSerializer,
)
from .validators import get_file_type_error


class FolderListCreateView(generics.ListCreateAPIView):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FolderTreeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        folders = list(Folder.objects.all().values("id", "name", "parent_id"))
        by_parent = {}
        for f in folders:
            by_parent.setdefault(f["parent_id"], []).append(f)

        def build(parent_id):
            return [
                {"id": f["id"], "name": f["name"], "children": build(f["id"])}
                for f in by_parent.get(parent_id, [])
            ]

        return Response(build(None))


class DocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return DocumentCreateSerializer if self.request.method == "POST" else DocumentListSerializer

    def get_queryset(self):
        qs = visible_documents_for(self.request.user).select_related("owner", "folder").prefetch_related("tags")
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(code__icontains=q)
                | Q(tags__name__icontains=q)
            ).distinct()
        if folder_id := params.get("folder"):
            qs = qs.filter(folder_id=folder_id)
        if status_filter := params.get("status"):
            qs = qs.filter(status=status_filter)
        if owner_id := params.get("owner"):
            qs = qs.filter(owner_id=owner_id)
        if tag := params.get("tag"):
            qs = qs.filter(tags__name__iexact=tag)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        audit_log(request.user, "upload", document=document, version=1)
        return Response(DocumentDetailSerializer(document).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DocumentDetailSerializer

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT"):
            return [permissions.IsAuthenticated(), HasDocumentPermission("edit")]
        if self.request.method == "DELETE":
            return [permissions.IsAuthenticated(), HasDocumentPermission("edit")]
        return [permissions.IsAuthenticated(), HasDocumentPermission("view")]

    def get_document(self):
        if not hasattr(self, "_document"):
            self._document = get_object_or_404(Document, pk=self.kwargs["pk"])
        return self._document

    def get_object(self):
        document = self.get_document()
        self.check_object_permissions(self.request, document)
        return document

    def retrieve(self, request, *args, **kwargs):
        document = self.get_object()
        audit_log(request.user, "view", document=document)
        return super().retrieve(request, *args, **kwargs)

    def perform_update(self, serializer):
        before = {"title": serializer.instance.title, "folder_id": serializer.instance.folder_id}
        document = serializer.save()
        audit_log(
            self.request.user, "edit_metadata", document=document,
            before=before, after={"title": document.title, "folder_id": document.folder_id},
        )

    def perform_destroy(self, instance):
        audit_log(self.request.user, "delete", target_repr=str(instance))
        instance.delete()


class DocumentVersionUploadView(generics.CreateAPIView):
    serializer_class = DocumentVersionSerializer
    permission_classes = [permissions.IsAuthenticated, HasDocumentPermission("edit")]

    def get_document(self):
        if not hasattr(self, "_document"):
            self._document = get_object_or_404(Document, pk=self.kwargs["pk"])
        return self._document

    def create(self, request, *args, **kwargs):
        document = self.get_document()
        self.check_object_permissions(request, document)
        file_obj = request.data.get("file")
        if not file_obj:
            raise ValidationError({"file": "This field is required."})
        file_error = get_file_type_error(file_obj)
        if file_error:
            raise ValidationError({"file": file_error})

        next_version = (document.latest_version.version_number + 1) if document.latest_version else 1
        checksum = DocumentVersion.compute_checksum(file_obj)
        file_obj.seek(0)
        with transaction.atomic():
            version = DocumentVersion.objects.create(
                document=document,
                version_number=next_version,
                file=file_obj,
                uploaded_by=request.user,
                change_note=request.data.get("change_note", ""),
                size=file_obj.size,
                checksum=checksum,
            )
            audit_log(request.user, "new_version", document=document, version=next_version, checksum=checksum)
        return Response(DocumentVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasDocumentPermission("download")]

    def get_document(self):
        if not hasattr(self, "_document"):
            self._document = get_object_or_404(Document, pk=self.kwargs["pk"])
        return self._document

    def get(self, request, pk):
        document = self.get_document()
        self.check_object_permissions(request, document)
        version_number = request.query_params.get("version")
        if version_number:
            version = get_object_or_404(document.versions, version_number=version_number)
        else:
            version = document.latest_version
        if not version:
            raise Http404("No versions available for this document.")

        audit_log(request.user, "download", document=document, version=version.version_number)
        return FileResponse(
            version.file.open("rb"), as_attachment=True, filename=version.file.name.split("/")[-1]
        )


class DocumentPermissionListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_document(self):
        if not hasattr(self, "_document"):
            self._document = get_object_or_404(Document, pk=self.kwargs["pk"])
        return self._document

    def _require_manage_rights(self, request, document):
        user = request.user
        is_manager = user.is_superuser or user.role == user.ROLE_ADMIN or document.owner_id == user.id
        if not is_manager:
            raise PermissionDenied("Only the owner or an admin can manage permissions for this document.")

    def get_queryset(self):
        document = self.get_document()
        self._require_manage_rights(self.request, document)
        return document.permissions.select_related("user", "group", "granted_by")

    def perform_create(self, serializer):
        document = self.get_document()
        self._require_manage_rights(self.request, document)
        grant = serializer.save(document=document, granted_by=self.request.user)
        audit_log(
            self.request.user, "permission_grant", document=document,
            grantee=grant.user.username if grant.user else f"group:{grant.group.name}",
            can_view=grant.can_view, can_edit=grant.can_edit,
            can_approve=grant.can_approve, can_download=grant.can_download,
            expires_at=grant.expires_at.isoformat() if grant.expires_at else None,
        )
        if grant.can_approve and grant.user:
            self._create_review_obligation(document, grant.user)

    def _create_review_obligation(self, document, reviewer):
        """A can_approve grant isn't just passive access - it's asking the
        grantee to actually review the document, so it creates the same
        pending ReviewAssignment that "submit for review" would."""
        latest = document.latest_version
        if not latest:
            return
        assignment, created = ReviewAssignment.objects.get_or_create(
            document=document, version=latest, reviewer=reviewer,
            status=ReviewAssignment.STATUS_PENDING,
            defaults={"assigned_by": self.request.user},
        )
        if created:
            if document.status != Document.STATUS_IN_REVIEW:
                document.status = Document.STATUS_IN_REVIEW
                document.save(update_fields=["status"])
            audit_log(
                self.request.user, "submit_for_review", document=document,
                version=latest.version_number, reviewers=[reviewer.username],
                via="permission_grant",
            )


class DocumentPermissionDeleteView(generics.DestroyAPIView):
    serializer_class = DocumentPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        grant = get_object_or_404(
            DocumentPermission, pk=self.kwargs["perm_pk"], document_id=self.kwargs["pk"]
        )
        user = self.request.user
        is_admin = user.is_superuser or user.role == user.ROLE_ADMIN
        if not is_admin:
            raise PermissionDenied("Only an admin can revoke permissions.")
        return grant

    def perform_destroy(self, instance):
        document = instance.document
        grantee = instance.user.username if instance.user else f"group:{instance.group.name}"
        instance.delete()
        audit_log(self.request.user, "permission_revoke", document=document, grantee=grantee)


class DocumentAuditView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasDocumentPermission("view")]

    def get_document(self):
        if not hasattr(self, "_document"):
            self._document = get_object_or_404(Document, pk=self.kwargs["pk"])
        return self._document

    def get(self, request, pk):
        document = self.get_document()
        self.check_object_permissions(request, document)
        entries = AuditLog.objects.filter(document=document).select_related("actor")
        return Response(AuditLogSerializer(entries, many=True).data)
