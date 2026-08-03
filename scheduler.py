import threading
from datetime import datetime
from typing import Callable, Optional

from config import AppConfig
from logger import setup_logger


class BackupScheduler:
    def __init__(self, callback: Callable[[], None], config: AppConfig, logger=None):
        self.callback = callback
        self.config = config
        self.logger = logger or setup_logger(config.log_file, config.log_level)
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._running = False
        self._last_scheduled_date = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("Daily backup scheduler started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.logger.info("Daily backup scheduler stopped")

    def is_started(self) -> bool:
        """Return whether this scheduler is currently running its loop."""
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.config = self._load_current_config()
            now = datetime.now()
            if self.config.schedule.lower() == "daily":
                target_hour, target_minute = self._backup_time()
                if (
                    now.hour == target_hour
                    and now.minute == target_minute
                    and self._last_scheduled_date != now.date()
                ):
                    self._last_scheduled_date = now.date()
                    self._execute_once()
                self._stop_event.wait(5)
            else:
                self._execute_once()
                self._stop_event.wait(60)

    def _load_current_config(self) -> AppConfig:
        """Reload local settings so changes take effect without a restart."""
        try:
            from config import load_config

            return load_config()
        except (OSError, ValueError) as exc:
            self.logger.error("Unable to reload settings: %s", exc)
            return self.config

    def _backup_time(self) -> tuple[int, int]:
        """Return the configured daily backup hour and minute."""
        try:
            hour, minute = (int(value) for value in self.config.backup_time.split(":"))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        except ValueError:
            pass
        self.logger.error("Invalid backup time %r; using 02:00", self.config.backup_time)
        return 2, 0

    def _execute_once(self) -> None:
        with self._lock:
            if self._running:
                self.logger.warning("Backup already running; skipping duplicate execution")
                return
            self._running = True

        try:
            self.logger.info("Starting scheduled backup")
            self.callback()
        except Exception as exc:
            self.logger.error("Scheduled backup failed: %s", exc)
        finally:
            with self._lock:
                self._running = False
