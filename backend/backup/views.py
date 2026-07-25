import secrets

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from audit.models import log as audit_log

from .services import RestoreError, build_backup, restore_backup, run_scheduled_backup


class BackupExportView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        buffer = build_backup(created_by=request.user)
        filename = f"docmanage-backup-{timezone.now().strftime('%Y%m%d-%H%M%S')}.zip"
        audit_log(request.user, "backup_export", target_repr=filename)
        return FileResponse(
            buffer, as_attachment=True, filename=filename, content_type="application/zip"
        )


class BackupImportView(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.data.get("file")
        if not file_obj:
            return Response({"detail": "No backup file was uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = restore_backup(file_obj)
        except RestoreError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Restoring just replaced the whole audit table with the backup's
        # history, so log this as a fresh entry on top of it. Best-effort:
        # if the acting admin's own account wasn't part of the backup being
        # restored, their user row - and this FK - may no longer exist.
        try:
            audit_log(request.user, "backup_restore", target_repr=file_obj.name, **result["counts"])
        except Exception:
            pass

        return Response(result, status=status.HTTP_200_OK)


class BackupCronView(APIView):
    """Scheduled-backup trigger for serverless hosting (Vercel Cron), where
    no long-lived process exists for the in-process timer. Vercel calls this
    on the schedule in vercel.json with `Authorization: Bearer <CRON_SECRET>`.

    Auth is the shared CRON_SECRET, not a user JWT - authentication_classes
    is emptied so simplejwt doesn't reject the non-JWT bearer token before
    we can compare it ourselves. 404s when no CRON_SECRET is configured, so
    the endpoint effectively doesn't exist outside cron-based deployments."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        secret = getattr(settings, "CRON_SECRET", "")
        if not secret:
            return Response(status=status.HTTP_404_NOT_FOUND)

        header = request.headers.get("Authorization", "")
        if not secrets.compare_digest(header, f"Bearer {secret}"):
            return Response(status=status.HTTP_403_FORBIDDEN)

        destination, pruned = run_scheduled_backup()
        audit_log(None, "backup_export", target_repr=str(destination))
        return Response({"written": str(destination), "pruned": [str(p) for p in pruned]})
