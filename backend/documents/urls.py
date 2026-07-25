from django.urls import path

from .views import (
    DocumentAuditView,
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListCreateView,
    DocumentPermissionDeleteView,
    DocumentPermissionListCreateView,
    DocumentVersionUploadView,
    FolderListCreateView,
    FolderTreeView,
)

urlpatterns = [
    path("folders/", FolderListCreateView.as_view(), name="folder-list"),
    path("folders/tree/", FolderTreeView.as_view(), name="folder-tree"),
    path("documents/", DocumentListCreateView.as_view(), name="document-list"),
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("documents/<int:pk>/versions/", DocumentVersionUploadView.as_view(), name="document-versions"),
    path("documents/<int:pk>/download/", DocumentDownloadView.as_view(), name="document-download"),
    path(
        "documents/<int:pk>/permissions/",
        DocumentPermissionListCreateView.as_view(),
        name="document-permissions",
    ),
    path(
        "documents/<int:pk>/permissions/<int:perm_pk>/",
        DocumentPermissionDeleteView.as_view(),
        name="document-permission-delete",
    ),
    path("documents/<int:pk>/audit/", DocumentAuditView.as_view(), name="document-audit"),
]
