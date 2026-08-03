import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd


@dataclass
class Device:
    hostname: str
    ip: str
    vendor: str
    credential_profile: str
    port: int | None = None


SUPPORTED_VENDORS = {"cisco", "juniper"}


def _split_host_and_port(value: str) -> tuple[str, int | None]:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Missing IP")

    if candidate.startswith("["):
        end = candidate.find("]")
        if end == -1:
            raise ValueError(f"Invalid IP: {value}")
        host = candidate[1:end]
        suffix = candidate[end + 1 :]
        if not suffix:
            return host, None
        if not suffix.startswith(":"):
            raise ValueError(f"Invalid IP: {value}")
        port_text = suffix[1:]
        if not port_text.isdigit():
            raise ValueError(f"Invalid IP: {value}")
        return host, int(port_text)

    if candidate.count(":") == 1:
        host, port_text = candidate.rsplit(":", 1)
        if not host or not port_text.isdigit():
            raise ValueError(f"Invalid IP: {value}")
        return host, int(port_text)

    return candidate, None


def _validate_device(row: dict) -> Device:
    hostname = str(row.get("hostname", "")).strip()
    ip = str(row.get("ip", "")).strip()
    vendor = str(row.get("vendor", "")).strip().lower()
    credential_profile = str(row.get("credential_profile", "")).strip()

    if not hostname:
        raise ValueError("Missing hostname")
    if not credential_profile:
        raise ValueError("Missing credential_profile")

    host, port = _split_host_and_port(ip)
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(f"Invalid IP: {ip}") from exc

    if vendor not in SUPPORTED_VENDORS:
        raise ValueError(f"Unsupported vendor: {vendor}")
    return Device(hostname=hostname, ip=host, vendor=vendor, credential_profile=credential_profile, port=port)


def load_devices(path: Path | str | None = None) -> List[Device]:
    csv_path = Path(path or Path(__file__).resolve().parent / "data" / "devices.csv")
    dataframe = pd.read_csv(csv_path)

    devices = []
    seen = set()
    for _, row in dataframe.iterrows():
        device = _validate_device(row)
        key = (device.hostname, device.ip)
        if key in seen:
            raise ValueError(f"Duplicate device detected: {device.hostname}")
        seen.add(key)
        devices.append(device)
    return devices
