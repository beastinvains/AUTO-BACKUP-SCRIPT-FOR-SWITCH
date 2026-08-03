"""Typed models used by the daily reporting engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CommandResult:
    """The result of one operational command executed on a device."""

    command: str
    status: str
    execution_time: float
    output: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without empty optional fields."""
        result = asdict(self)
        return {key: value for key, value in result.items() if value is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandResult":
        """Create a command result from a saved report document."""
        return cls(
            command=str(data["command"]),
            status=str(data["status"]),
            execution_time=float(data["execution_time"]),
            output=str(data.get("output", "")),
            error=data.get("error"),
        )


@dataclass
class DeviceReport:
    """Operational report data for one device in a daily report."""

    hostname: str
    ip: str
    vendor: str
    status: str
    backup_file: str | None = None
    commands: list[CommandResult] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for the Web UI contract."""
        result: dict[str, Any] = {
            "hostname": self.hostname,
            "ip": self.ip,
            "vendor": self.vendor,
            "status": self.status,
            "commands": [command.to_dict() for command in self.commands],
            "metadata": self.metadata,
        }
        if self.backup_file is not None:
            result["backup_file"] = self.backup_file
        if self.error is not None:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceReport":
        """Create a device report from a saved report document."""
        return cls(
            hostname=str(data["hostname"]),
            ip=str(data["ip"]),
            vendor=str(data.get("vendor", "")),
            status=str(data["status"]),
            backup_file=data.get("backup_file"),
            commands=[CommandResult.from_dict(command) for command in data.get("commands", [])],
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DailyReport:
    """The versioned, daily JSON document consumed by future user interfaces."""

    report_date: str
    generated_at: str
    devices: list[DeviceReport] = field(default_factory=list)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Build the stable JSON document and calculate its summary statistics."""
        successful = sum(device.status.lower() == "success" for device in self.devices)
        failed = sum(device.status.lower() == "failed" for device in self.devices)
        return {
            "schema_version": self.schema_version,
            "report_date": self.report_date,
            "generated_at": self.generated_at,
            "statistics": {
                "total_devices": len(self.devices),
                "successful": successful,
                "failed": failed,
            },
            "devices": [device.to_dict() for device in self.devices],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyReport":
        """Load a daily report while tolerating fields added by future versions."""
        return cls(
            report_date=str(data["report_date"]),
            generated_at=str(data["generated_at"]),
            devices=[DeviceReport.from_dict(device) for device in data.get("devices", [])],
            schema_version=int(data.get("schema_version", 1)),
            metadata=dict(data.get("metadata", {})),
        )
