from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from audit.models import log as audit_log

from .services import RestoreError, build_backup, restore_backup


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
