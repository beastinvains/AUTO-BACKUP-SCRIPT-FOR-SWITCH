"""The single backup scheduler.

Phase 3 replaced the one hard-coded daily window with named schedule rows, so this
module is now only a clock: it wakes up, asks :class:`~schedule_service.ScheduleService`
which schedules are due, and lets that service run them through BackupService.  There
is deliberately no second scheduler and no second backup path.
"""

from __future__ import annotations

import threading

from logger import setup_logger

TICK_SECONDS = 30


class ScheduleRunner:
    """Polls for due schedules. Overlapping runs are skipped, not queued."""

    def __init__(self, schedules, logger=None, tick_seconds: int = TICK_SECONDS):
        self.schedules = schedules
        self.logger = logger or setup_logger()
        self.tick_seconds = tick_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        if self.is_started():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="schedule-runner")
        self._thread.start()
        self.logger.info("Backup schedule runner started (tick %ss)", self.tick_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.logger.info("Backup schedule runner stopped")

    def is_started(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def tick(self) -> list[dict]:
        """One scheduling pass; also the seam the tests drive instead of the thread."""
        with self._lock:
            if self._running:
                self.logger.warning("Previous scheduled backup still running; skipping this tick")
                return []
            self._running = True
        try:
            results = self.schedules.run_due()
            for result in results:
                self.logger.info("Schedule %s finished with %s (job %s)",
                                 result["schedule_id"], result["status"], result["job_id"])
            return results
        except Exception as exc:
            self.logger.error("Schedule tick failed: %s", exc)
            return []
        finally:
            with self._lock:
                self._running = False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.tick()
            self._stop_event.wait(self.tick_seconds)
