from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from backup.services import run_scheduled_backup


class Command(BaseCommand):
    help = (
        "Writes a full backup archive (database + files) and prunes old ones "
        "beyond the retention count. Destination follows BACKUP_STORAGE: 'local' "
        "writes into BACKUP_DIR, 'bucket' uploads to the file-storage bucket "
        "under BACKUP_S3_PREFIX. This command doesn't schedule itself - point "
        "cron / Windows Task Scheduler at it (see README), or set "
        "BACKUP_INTERVAL_SECONDS to run it automatically inside the server process."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention",
            type=int,
            default=None,
            help=f"How many backups to keep (default: settings.BACKUP_RETENTION = {settings.BACKUP_RETENTION}).",
        )

    def handle(self, *args, **options):
        destination, pruned = run_scheduled_backup(retention=options["retention"])
        if isinstance(destination, Path):
            detail = f" ({destination.stat().st_size / 1024:.1f} KB)"
        else:
            detail = " (uploaded to file storage)"
        self.stdout.write(self.style.SUCCESS(f"Wrote {destination}{detail}"))
        for stale in pruned:
            name = stale.name if isinstance(stale, Path) else stale
            self.stdout.write(f"Pruned old backup: {name}")
