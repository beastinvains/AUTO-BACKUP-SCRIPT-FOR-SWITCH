from pathlib import Path

import yaml

from core.models import DiscoveryTarget


def load_targets(path: str | Path) -> list[DiscoveryTarget]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    devices = payload.get("devices", [])
    if not isinstance(devices, list):
        raise ValueError("devices must be a list")
    return [DiscoveryTarget.model_validate(item) for item in devices]

