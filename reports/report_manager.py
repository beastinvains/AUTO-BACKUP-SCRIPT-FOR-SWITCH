"""Creation, aggregation, persistence, and loading of daily reports."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from reports.report_models import CommandResult, DailyReport, DeviceReport
from utils import ensure_directory


class ReportManager:
    """Thread-safe manager for one date's ``daily_report.json`` document."""

    def __init__(self, backup_root: Path | str, report_time: datetime | None = None):
        self.report_time = report_time or datetime.now()
        self.report_directory = self._build_report_directory(Path(backup_root), self.report_time)
        self.path = self.report_directory / "daily_report.json"
        self._lock = threading.Lock()
        self.report = self.load(self.path) if self.path.exists() else DailyReport(
            report_date=self.report_time.date().isoformat(),
            generated_at=self.report_time.isoformat(timespec="seconds"),
        )

    @staticmethod
    def _build_report_directory(backup_root: Path, report_time: datetime) -> Path:
        """Return the existing date directory without creating device folders."""
        return ensure_directory(
            backup_root
            / report_time.strftime("%Y")
            / report_time.strftime("%m-%B")
            / report_time.strftime("%Y-%m-%d")
        )

    def add_command(self, device_report: DeviceReport, result: CommandResult) -> None:
        """Attach an operational command result to a device report."""
        device_report.commands.append(result)

    def add_device(self, device_report: DeviceReport) -> None:
        """Add or replace one device, making repeat runs on a day idempotent."""
        with self._lock:
            for index, existing in enumerate(self.report.devices):
                if existing.hostname == device_report.hostname:
                    self.report.devices[index] = device_report
                    break
            else:
                self.report.devices.append(device_report)

    def backup_file_reference(self, file_path: Path) -> str:
        """Return a portable backup path relative to this date's report directory."""
        try:
            return str(file_path.relative_to(self.report_directory))
        except ValueError:
            return str(file_path)

    def save(self) -> Path:
        """Atomically persist the report so a Web UI never reads partial JSON."""
        with self._lock:
            self.report.generated_at = datetime.now().isoformat(timespec="seconds")
            document = self.report.to_dict()
            temporary_path = self.path.with_suffix(".json.tmp")
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temporary_path, self.path)
        return self.path

    @staticmethod
    def load(path: Path | str) -> DailyReport:
        """Load a previously written daily report for a future Web UI or rerun."""
        with open(path, "r", encoding="utf-8") as handle:
            return DailyReport.from_dict(json.load(handle))
