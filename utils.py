import os
from datetime import datetime
from pathlib import Path


def ensure_directory(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_backup_path(backup_root: Path | str, today: datetime, hostname: str) -> Path:
    root = Path(backup_root)
    year_folder = today.strftime("%Y")
    month_folder = today.strftime("%m-%B")
    day_folder = today.strftime("%Y-%m-%d")
    return ensure_directory(root / year_folder / month_folder / day_folder / hostname)


def normalize_vendor(vendor: str) -> str:
    return vendor.strip().lower()
