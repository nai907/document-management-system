from django.urls import path

from .views import BackupCronView, BackupExportView, BackupImportView

urlpatterns = [
    path("backup/export/", BackupExportView.as_view(), name="backup-export"),
    path("backup/import/", BackupImportView.as_view(), name="backup-import"),
    path("backup/cron/", BackupCronView.as_view(), name="backup-cron"),
]
