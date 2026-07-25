import io
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from backup.apps import should_start_scheduler
from documents.models import Document, DocumentPermission, DocumentVersion, Folder, Tag

User = get_user_model()


def make_file(name="handbook.txt", content=b"original contents"):
    return SimpleUploadedFile(name, content, content_type="text/plain")


class BackupRestoreTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass12345", role=User.ROLE_ADMIN)
        self.employee = User.objects.create_user("emp", password="pass12345")
        self.folder = Folder.objects.create(name="HR", created_by=self.admin)
        self.tag = Tag.objects.create(name="policy")
        self.document = Document.objects.create(title="Handbook", owner=self.employee, folder=self.folder)
        self.document.tags.add(self.tag)
        self.version = DocumentVersion.objects.create(
            document=self.document, version_number=1, file=make_file(),
            uploaded_by=self.employee, size=18, checksum="x",
        )
        DocumentPermission.objects.create(
            document=self.document, user=self.employee, granted_by=self.admin,
            can_view=True, can_download=True,
        )

    def _export(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/backup/export/")
        self.assertEqual(resp.status_code, 200)
        return b"".join(resp.streaming_content)

    def test_export_produces_well_formed_archive(self):
        archive_bytes = self._export()
        zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
        names = zf.namelist()
        self.assertIn("manifest.json", names)
        self.assertTrue(any(n.startswith("files/documents/") for n in names))

    def test_restore_rebuilds_wiped_data_and_files(self):
        archive_bytes = self._export()

        DocumentPermission.objects.all().delete()
        DocumentVersion.objects.all().delete()
        Document.objects.all().delete()
        Tag.objects.all().delete()
        Folder.objects.all().delete()

        upload = SimpleUploadedFile("backup.zip", archive_bytes, content_type="application/zip")
        resp = self.client.post("/api/backup/import/", {"file": upload}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.data)

        restored = Document.objects.get(title="Handbook")
        self.assertEqual(restored.owner_id, self.employee.id)
        self.assertEqual(restored.folder.name, "HR")
        self.assertEqual(list(restored.tags.values_list("name", flat=True)), ["policy"])

        version = restored.latest_version
        self.assertIsNotNone(version)
        with version.file.open("rb") as fh:
            self.assertEqual(fh.read(), b"original contents")

        self.assertTrue(
            DocumentPermission.objects.filter(document=restored, user=self.employee, can_view=True).exists()
        )

    def test_non_admin_cannot_export(self):
        self.client.force_authenticate(self.employee)
        resp = self.client.get("/api/backup/export/")
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_cannot_import(self):
        self.client.force_authenticate(self.employee)
        upload = SimpleUploadedFile("backup.zip", b"irrelevant", content_type="application/zip")
        resp = self.client.post("/api/backup/import/", {"file": upload}, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_restore_rejects_non_zip_file(self):
        self.client.force_authenticate(self.admin)
        upload = SimpleUploadedFile("notazip.zip", b"just some plain text", content_type="application/zip")
        resp = self.client.post("/api/backup/import/", {"file": upload}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("valid backup archive", resp.data["detail"])

    def test_restore_rejects_zip_missing_manifest(self):
        self.client.force_authenticate(self.admin)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("hello.txt", "not a real backup")
        buffer.seek(0)
        upload = SimpleUploadedFile("backup.zip", buffer.read(), content_type="application/zip")
        resp = self.client.post("/api/backup/import/", {"file": upload}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("manifest.json", resp.data["detail"])

    def test_original_data_untouched_when_export_only(self):
        self._export()
        self.assertTrue(Document.objects.filter(title="Handbook").exists())


class RunBackupCommandTests(TestCase):
    def setUp(self):
        User.objects.create_user("owner", password="pass12345")

    def test_writes_one_valid_archive_to_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(BACKUP_DIR=tmpdir):
                call_command("run_backup")

            files = list(Path(tmpdir).glob("docmanage-backup-*.zip"))
            self.assertEqual(len(files), 1)
            with zipfile.ZipFile(files[0]) as zf:
                self.assertIn("manifest.json", zf.namelist())

    def test_retention_prunes_older_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(BACKUP_DIR=tmpdir):
                for _ in range(4):
                    call_command("run_backup", retention=2)

            files = sorted(Path(tmpdir).glob("docmanage-backup-*.zip"))
            self.assertEqual(len(files), 2)


class BucketBackupTests(TestCase):
    """Runs bucket-mode backups against FileSystemStorage pointed at a temp
    dir - same default_storage code path the S3 backend goes through,
    without touching a real bucket from the test suite."""

    def _bucket_settings(self, tmpdir):
        return override_settings(
            MEDIA_ROOT=tmpdir,
            STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
            BACKUP_STORAGE="bucket",
        )

    def test_uploads_archive_under_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self._bucket_settings(tmpdir):
                call_command("run_backup")

            files = list((Path(tmpdir) / "backups").glob("docmanage-backup-*.zip"))
            self.assertEqual(len(files), 1)
            with zipfile.ZipFile(files[0]) as zf:
                self.assertIn("manifest.json", zf.namelist())

    def test_retention_prunes_older_bucket_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self._bucket_settings(tmpdir):
                for _ in range(4):
                    call_command("run_backup", retention=2)

            files = list((Path(tmpdir) / "backups").glob("docmanage-backup-*.zip"))
            self.assertEqual(len(files), 2)

    def test_local_mode_still_writes_to_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(BACKUP_DIR=tmpdir, BACKUP_STORAGE="local"):
                call_command("run_backup")

            files = list(Path(tmpdir).glob("docmanage-backup-*.zip"))
            self.assertEqual(len(files), 1)


class BackupCronViewTests(APITestCase):
    def test_404_when_no_cron_secret_configured(self):
        with override_settings(CRON_SECRET=""):
            resp = self.client.get("/api/backup/cron/")
        self.assertEqual(resp.status_code, 404)

    def test_403_on_wrong_secret(self):
        with override_settings(CRON_SECRET="topsecret"):
            resp = self.client.get("/api/backup/cron/", HTTP_AUTHORIZATION="Bearer wrong")
        self.assertEqual(resp.status_code, 403)

    def test_correct_secret_writes_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(CRON_SECRET="topsecret", BACKUP_STORAGE="local", BACKUP_DIR=tmpdir):
                resp = self.client.get("/api/backup/cron/", HTTP_AUTHORIZATION="Bearer topsecret")
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(len(list(Path(tmpdir).glob("docmanage-backup-*.zip"))), 1)


class ShouldStartSchedulerTests(TestCase):
    def test_management_commands_are_excluded(self):
        for command in ("test", "migrate", "makemigrations", "seed_demo", "run_backup", "shell"):
            self.assertFalse(should_start_scheduler(["manage.py", command], run_main_env=None))

    def test_runserver_outer_autoreload_watcher_is_excluded(self):
        # No --noreload and RUN_MAIN unset: this is the watcher process that
        # re-execs itself, not the one that should own the timer.
        self.assertFalse(should_start_scheduler(["manage.py", "runserver"], run_main_env=None))

    def test_runserver_reloaded_child_process_is_included(self):
        self.assertTrue(should_start_scheduler(["manage.py", "runserver"], run_main_env="true"))

    def test_runserver_noreload_is_included(self):
        self.assertTrue(should_start_scheduler(["manage.py", "runserver", "--noreload"], run_main_env=None))

    def test_unknown_command_defaults_to_included(self):
        self.assertTrue(should_start_scheduler(["manage.py", "some_custom_command"], run_main_env=None))
