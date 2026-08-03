import os
import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPORT_COMMANDS = {
    "juniper": [
        "show chassis environment | no-more",
        "show version | no-more",
    ],
    "cisco": [
        "show environment",
        "show version",
    ],
}

SETTINGS_FILE = Path(__file__).resolve().parent / "config.json"


def _load_report_commands(value: str | None) -> dict[str, list[str]]:
    """Read optional JSON command configuration from ``REPORT_COMMANDS``."""
    if not value:
        return {vendor: list(commands) for vendor, commands in DEFAULT_REPORT_COMMANDS.items()}
    try:
        commands = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("REPORT_COMMANDS must be valid JSON") from exc
    if not isinstance(commands, dict) or not all(
        isinstance(vendor, str)
        and isinstance(vendor_commands, list)
        and all(isinstance(command, str) and command.strip() for command in vendor_commands)
        for vendor, vendor_commands in commands.items()
    ):
        raise ValueError("REPORT_COMMANDS must be a JSON object of vendor command lists")
    return {vendor.lower(): list(vendor_commands) for vendor, vendor_commands in commands.items()}


@dataclass
class AppConfig:
    backup_root: Path
    devices_file: Path
    env_file: Path
    log_file: Path
    log_level: str = "INFO"
    schedule: str = "daily"
    retry_count: int = 3
    timeout: int = 60
    banner_timeout: int = 15
    max_workers: int = 4
    backup_time: str = "02:00"
    retention_days: int = 30
    report_commands: dict[str, list[str]] | None = None


def _default_backup_root() -> Path:
    if os.name == "nt":
        return Path(r"C:\Users\Backup\OneDrive\NetworkBackups")
    return Path.home() / "NetworkBackups"


def load_settings(path: Path = SETTINGS_FILE) -> dict[str, object]:
    """Load local UI settings without creating or changing the settings file."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            settings = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid settings file: {path}") from exc
    if not isinstance(settings, dict):
        raise ValueError("config.json must contain a JSON object")
    return settings


def load_config() -> AppConfig:
    base_dir = Path(__file__).resolve().parent
    settings = load_settings()
    backup_root = Path(os.environ.get(
        "BACKUP_ROOT", str(settings.get("backup_directory", _default_backup_root()))
    )).expanduser()
    devices_file = Path(os.environ.get("DEVICES_FILE", str(base_dir / "data" / "devices.csv")))
    env_file = Path(os.environ.get("ENV_FILE", str(base_dir / ".env")))
    log_file = Path(os.environ.get("LOG_FILE", str(base_dir / "logs" / "backup.log")))

    return AppConfig(
        backup_root=backup_root,
        devices_file=devices_file,
        env_file=env_file,
        log_file=log_file,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        schedule=os.environ.get("SCHEDULE", "daily"),
        retry_count=int(os.environ.get("RETRY_COUNT", "3")),
        timeout=int(os.environ.get("TIMEOUT", "60")),
        banner_timeout=int(os.environ.get("BANNER_TIMEOUT", "15")),
        max_workers=int(os.environ.get("MAX_WORKERS", settings.get("max_workers", 4))),
        backup_time=str(settings.get("backup_time", "02:00")),
        retention_days=int(settings.get("retention_days", 30)),
        report_commands=_load_report_commands(os.environ.get("REPORT_COMMANDS")),
    )
