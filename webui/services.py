"""Read-only report/log access and background backup orchestration."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from config import SETTINGS_FILE, load_config, load_settings


def latest_report() -> dict[str, Any]:
    """Return the newest daily report, or an empty report when none exists."""
    try:
        paths = list(load_config().backup_root.rglob("daily_report.json"))
    except OSError:
        paths = []
    if not paths:
        return {"devices": [], "statistics": {}}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"devices": [], "statistics": {}}
    return report if isinstance(report, dict) else {"devices": [], "statistics": {}}


def recent_reports(limit: int = 3) -> list[dict[str, Any]]:
    """Load up to ``limit`` recent daily reports for UI-only comparisons."""
    try:
        paths = sorted(
            load_config().backup_root.rglob("daily_report.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:limit]
    except OSError:
        return []
    reports: list[dict[str, Any]] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                report = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(report, dict):
            reports.append(report)
    return reports


def report_devices(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return valid device records from a report document."""
    return [item for item in report.get("devices", []) if isinstance(item, dict)]


def next_backup_at(backup_time: str) -> datetime | None:
    """Calculate the next configured daily backup time."""
    try:
        target = datetime.strptime(backup_time, "%H:%M").time()
    except ValueError:
        return None
    now = datetime.now()
    result = datetime.combine(now.date(), target)
    return result if result > now else result + timedelta(days=1)


def save_settings(settings: dict[str, object]) -> None:
    """Atomically save UI-editable settings to config.json."""
    temporary = SETTINGS_FILE.with_suffix(".json.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    temporary.replace(SETTINGS_FILE)


def current_settings() -> dict[str, object]:
    """Return persisted UI settings."""
    config = load_config()
    stored = load_settings()
    return {
        "backup_time": stored.get("backup_time", config.backup_time),
        "backup_directory": stored.get("backup_directory", str(config.backup_root)),
        "max_workers": stored.get("max_workers", config.max_workers),
        "retention_days": stored.get("retention_days", config.retention_days),
    }


def filtered_log_lines(level: str, query: str) -> list[str]:
    """Read matching lines from the existing application log file only."""
    try:
        with open(load_config().log_file, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-2000:]
    except OSError:
        return []
    return [line.rstrip("\n") for line in lines if (not level or f" {level} " in line) and (not query or query.casefold() in line.casefold())]


class BackupRunner:
    """Run the existing backup engine once at a time for the local UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started_at: datetime | None = None
        self._started_tick: float | None = None
        self._message = "Idle"

    def start(self) -> bool:
        """Start a background backup, unless one is already active."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._started_at, self._started_tick = datetime.now(), monotonic()
            self._message = "Backup is running"
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return True

    def status(self) -> dict[str, object]:
        """Return safe progress information for browser polling."""
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            elapsed = monotonic() - self._started_tick if running and self._started_tick else 0
            return {"running": running, "message": self._message, "elapsed_seconds": round(elapsed)}

    def _run(self) -> None:
        """Delegate directly to the existing backup entry points."""
        try:
            from backup import backup_devices
            from credentials import load_environment
            from devices import load_devices
            from logger import setup_logger

            config = load_config()
            load_environment(config.env_file)
            logger = setup_logger(config.log_file, config.log_level)
            results = backup_devices(load_devices(config.devices_file), config, logger)
            successful = sum(item.get("status") == "success" for item in results)
            message = f"Finished: {successful}/{len(results)} successful"
        except Exception as exc:
            message = f"Backup failed: {exc}"
        with self._lock:
            self._message = message
