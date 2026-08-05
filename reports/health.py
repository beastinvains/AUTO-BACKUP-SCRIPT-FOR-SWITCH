"""Health parsing helpers for daily report command output."""

from __future__ import annotations

import re
from typing import Any

_POWER_SUPPLY_LINE = re.compile(
    r"(?ix)"
    r"\b(?P<name>(?:FPC\s*\d+\s+)?power\s+supply(?:\s+[A-Za-z0-9]+)?)\b"
    r"[\s:,-]*"
    r"(?:is\s+)?"
    r"(?P<status>OK|Present|Absent|Not\s+Present|Failed|Unknown)\b"
)

_NORMALIZED_STATUS = {
    "ok": "OK",
    "present": "Present",
    "not present": "Not Present",
    "absent": "Absent",
    "failed": "Failed",
    "unknown": "Unknown",
}

_FAILED_STATUSES = {"Failed"}


def _canonical_name(value: str, keep_fpc: bool = False) -> str:
    value = re.sub(r"\s+", " ", value.strip(), flags=re.I)
    if not keep_fpc:
        value = re.sub(r"(?ix)^fpc\s+\d+\s+", "", value)
    value = value.title()
    if not keep_fpc:
        value = re.sub(r"\bFpc\b", "FPC", value)
    return value


def _normalize_status(value: str) -> str:
    normalized = re.sub(r"^\s*is\s+", "", value.strip(), flags=re.I)
    normalized = re.sub(r"\s+", " ", normalized)
    key = normalized.lower()
    return _NORMALIZED_STATUS.get(key, normalized.title())


def parse_power_supplies(output: str) -> dict[str, Any]:
    """Parse unique power supplies and return structured status information."""
    # If the output contains multiple FPC instances, keep the FPC prefix
    # in the parsed supply name so we don't collapse per-unit supplies.
    fpc_ids = set()
    for line in output.splitlines():
        m = re.search(r"(?ix)\bfpc\s+(\d+)\b", line)
        if m:
            fpc_ids.add(m.group(1))
    keep_fpc = len(fpc_ids) > 1

    supplies: dict[str, str] = {}
    for line in output.splitlines():
        match = _POWER_SUPPLY_LINE.search(line)
        if not match:
            continue

        name = _canonical_name(match.group("name"), keep_fpc=keep_fpc)
        status = _normalize_status(match.group("status"))
        supplies[name] = status

    items = [{"name": name, "status": status} for name, status in supplies.items()]
    total = len(items)
    ok = sum(1 for status in supplies.values() if status == "OK")
    failed = sum(1 for status in supplies.values() if status in _FAILED_STATUSES)
    warning = total - ok - failed

    return {
        "total": total,
        "ok": ok,
        "failed": failed,
        "warning": warning,
        "items": items,
    }


def parse_power_supplies_from_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate power supply data from a list of command result objects."""
    combined = []
    for result in results:
        output = result.get("output") or ""
        if output:
            combined.append(output)
        error = result.get("error") or ""
        if error:
            combined.append(error)
    return parse_power_supplies("\n".join(combined))
