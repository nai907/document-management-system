from django.urls import path

from .views import BackupExportView, BackupImportView

urlpatterns = [
    path("backup/export/", BackupExportView.as_view(), name="backup-export"),
    path("backup/import/", BackupImportView.as_view(), name="backup-import"),
]
