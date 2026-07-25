import logging
import threading
import time

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_started = False


def start_periodic_backup(interval_seconds):
    """Starts a single daemon thread that writes a backup to disk every
    interval_seconds for as long as this process is alive. Idempotent - a
    second call is a no-op, so callers don't need to track whether they
    already started it.

    This only covers a single process: it's the right fit for `manage.py
    runserver`, but a multi-worker production server (e.g. several gunicorn
    workers) would start one independent timer per worker and write
    duplicate backups. For that case, use the OS-level scheduler instead
    (`manage.py run_backup` via cron / Task Scheduler)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def loop():
        # Local import: avoids touching Django's app registry / settings
        # before it's fully populated, since this runs from AppConfig.ready().
        from .services import run_scheduled_backup

        while True:
            time.sleep(interval_seconds)
            try:
                destination, pruned = run_scheduled_backup()
                logger.info("Periodic backup written to %s (pruned %d)", destination, len(pruned))
            except Exception:
                logger.exception("Periodic backup failed")

    threading.Thread(target=loop, name="backup-scheduler", daemon=True).start()
