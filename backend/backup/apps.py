import os
import sys

from django.apps import AppConfig

# Commands that never mean "the app is serving requests" - ready() runs for
# every management command, and we only want the periodic backup timer
# starting once, in the actual server process.
NON_SERVER_COMMANDS = {
    "test", "migrate", "makemigrations", "seed_demo", "run_backup",
    "shell", "shell_plus", "createsuperuser", "collectstatic", "dbshell", "check",
}


def should_start_scheduler(argv, run_main_env):
    """Pure decision logic, kept separate from ready() so it's testable
    without actually launching management commands or a server process."""
    command = argv[1] if len(argv) > 1 else None
    if command in NON_SERVER_COMMANDS:
        return False
    if command == "runserver" and "--noreload" not in argv and run_main_env != "true":
        # This is the autoreloader's outer watcher process; it re-execs
        # itself into a child with RUN_MAIN=true, which is the one that
        # should actually start the timer (avoids starting it twice).
        return False
    return True


class BackupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backup"

    def ready(self):
        from django.conf import settings

        interval = getattr(settings, "BACKUP_INTERVAL_SECONDS", 0)
        if not interval:
            return
        if not should_start_scheduler(sys.argv, os.environ.get("RUN_MAIN")):
            return

        from .scheduler import start_periodic_backup
        start_periodic_backup(interval)
