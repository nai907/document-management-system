import io
import json
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.serializers import deserialize, serialize
from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from documents.models import Document, DocumentPermission, DocumentVersion, Folder, Tag
from reviews.models import ReviewAssignment

User = get_user_model()

FORMAT_VERSION = 1
FILENAME_PREFIX = "docmanage-backup-"

# Parent-first: a full restore wipes every table and reinserts from these
# fixtures in this exact order, so anything a later model references by
# foreign key (folder parents, document owners, permission grantees, ...)
# already exists in the database by the time it's needed.
MODEL_ORDER = [
    ("auth.Group", Group),
    ("accounts.User", User),
    ("documents.Folder", Folder),
    ("documents.Tag", Tag),
    ("documents.Document", Document),
    ("documents.DocumentVersion", DocumentVersion),
    ("documents.DocumentPermission", DocumentPermission),
    ("reviews.ReviewAssignment", ReviewAssignment),
    ("audit.AuditLog", AuditLog),
]


class RestoreError(Exception):
    """Raised for a malformed or incompatible backup archive - always safe
    to show str(e) directly to the admin who uploaded it."""


def _ordered_folders():
    """Folders self-reference via `parent`. A plain queryset dump can list a
    child before its own parent, which breaks a parent-first restore. Walk
    the tree breadth-first from the roots instead so parents always sort
    before their children."""
    by_parent = {}
    for folder in Folder.objects.all():
        by_parent.setdefault(folder.parent_id, []).append(folder)
    ordered = []
    queue = list(by_parent.get(None, []))
    while queue:
        node = queue.pop(0)
        ordered.append(node)
        queue.extend(by_parent.get(node.id, []))
    return ordered


def _objects_for(model):
    return _ordered_folders() if model is Folder else list(model.objects.all())


def build_backup(created_by):
    """Returns a BytesIO holding a zip: one JSON fixture per model (in
    MODEL_ORDER), the raw bytes of every document file under files/, and a
    manifest describing what's inside."""
    buffer = io.BytesIO()
    counts = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, (label, model) in enumerate(MODEL_ORDER, start=1):
            objects = _objects_for(model)
            counts[label] = len(objects)
            zf.writestr(f"data/{index:02d}_{label}.json", serialize("json", objects))

        file_count = 0
        missing_files = []
        for version in DocumentVersion.objects.all():
            if not version.file:
                continue
            try:
                with version.file.open("rb") as fh:
                    zf.writestr(f"files/{version.file.name}", fh.read())
                file_count += 1
            except OSError:
                # Storage and the database have drifted for this row (the
                # key it points to no longer exists in the backend) - note
                # it and keep going rather than letting one bad row take
                # down the entire backup.
                missing_files.append(version.file.name)

        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": timezone.now().isoformat(),
            "created_by": created_by.username if created_by else None,
            "model_order": [label for label, _ in MODEL_ORDER],
            "counts": counts,
            "file_count": file_count,
            "missing_files": missing_files,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    buffer.seek(0)
    return buffer


def write_backup_to_disk(backup_dir=None, retention=None, created_by=None):
    """Builds a backup and writes it straight to disk under backup_dir,
    pruning older archives beyond retention. Shared by `manage.py run_backup`
    and the in-process periodic scheduler, so both write identical archives
    and apply identical retention. Returns (path_written, paths_pruned)."""
    backup_dir = Path(backup_dir or settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    retention = settings.BACKUP_RETENTION if retention is None else retention

    buffer = build_backup(created_by=created_by)
    filename = f"{FILENAME_PREFIX}{timezone.now().strftime('%Y%m%d-%H%M%S-%f')}.zip"
    path = backup_dir / filename
    path.write_bytes(buffer.read())

    pruned = []
    if retention > 0:
        existing = sorted(backup_dir.glob(f"{FILENAME_PREFIX}*.zip"), key=lambda p: p.name)
        for stale in existing[:-retention]:
            stale.unlink()
            pruned.append(stale)

    return path, pruned


def write_backup_to_bucket(retention=None, created_by=None):
    """Builds a backup and uploads it to the default file storage (the S3
    bucket when one is configured, media/ on local disk otherwise) under
    BACKUP_S3_PREFIX, pruning older archives beyond retention. Unlike a
    local BACKUP_DIR, the bucket survives redeploys and instance restarts,
    which makes this the right destination on ephemeral-disk hosting.
    Returns (name_written, names_pruned)."""
    retention = settings.BACKUP_RETENTION if retention is None else retention
    prefix = settings.BACKUP_S3_PREFIX

    buffer = build_backup(created_by=created_by)
    filename = f"{FILENAME_PREFIX}{timezone.now().strftime('%Y%m%d-%H%M%S-%f')}.zip"
    name = default_storage.save(prefix + filename, ContentFile(buffer.read()))

    pruned = []
    if retention > 0:
        _, files = default_storage.listdir(prefix)
        existing = sorted(f for f in files if f.startswith(FILENAME_PREFIX) and f.endswith(".zip"))
        for stale in existing[:-retention]:
            default_storage.delete(prefix + stale)
            pruned.append(prefix + stale)

    return name, pruned


def run_scheduled_backup(retention=None, created_by=None):
    """Single entry point for both scheduled paths (the in-process timer
    and `manage.py run_backup`): writes wherever BACKUP_STORAGE says -
    'bucket' uploads to the file-storage bucket, anything else writes to
    local BACKUP_DIR. Returns (destination, pruned) like the two writers."""
    if settings.BACKUP_STORAGE == "bucket":
        return write_backup_to_bucket(retention=retention, created_by=created_by)
    return write_backup_to_disk(retention=retention, created_by=created_by)


def restore_backup(fileobj):
    """Wipes every backed-up table and every backed-up file's storage key,
    then reloads all of it from the archive. This is a full replace, not a
    merge - anything created since the backup was taken is gone afterwards."""
    try:
        zf = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        raise RestoreError("That file isn't a valid backup archive (not a zip).")

    try:
        manifest = json.loads(zf.read("manifest.json"))
    except KeyError:
        raise RestoreError("Archive is missing manifest.json - it wasn't produced by this system.")
    except json.JSONDecodeError:
        raise RestoreError("manifest.json in the archive is corrupted.")

    if manifest.get("format_version") != FORMAT_VERSION:
        raise RestoreError(
            f"Unsupported backup format version {manifest.get('format_version')!r} "
            f"(this build restores version {FORMAT_VERSION})."
        )

    with transaction.atomic():
        # Child-first wipe so no row is ever left pointing at a foreign key
        # that's about to disappear mid-restore.
        for _, model in reversed(MODEL_ORDER):
            model.objects.all().delete()

        restored_counts = {}
        for index, (label, model) in enumerate(MODEL_ORDER, start=1):
            entry_name = f"data/{index:02d}_{label}.json"
            try:
                raw = zf.read(entry_name)
            except KeyError:
                raise RestoreError(f"Archive is missing {entry_name}.")
            objects = list(deserialize("json", raw))
            for obj in objects:
                obj.save()
            restored_counts[label] = len(objects)

        restored_files = 0
        for name in zf.namelist():
            if not name.startswith("files/") or name == "files/":
                continue
            storage_name = name[len("files/"):]
            if default_storage.exists(storage_name):
                default_storage.delete(storage_name)
            default_storage.save(storage_name, ContentFile(zf.read(name)))
            restored_files += 1

    return {"counts": restored_counts, "file_count": restored_files, "manifest": manifest}
