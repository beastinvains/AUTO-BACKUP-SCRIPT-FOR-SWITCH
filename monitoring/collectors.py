"""
Phase 4 — Monitoring Collectors.

Vendor-neutral collection layer.  No CLI command strings live here;
they stay inside the vendor adapters.  Each collector calls the
adapter's public API and returns a normalized CollectionResult.

Failure on one device MUST NOT stop collection on others — each
collector method is independent and catches its own exceptions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.models import Health, Interface

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TelemetryResult:
    device_id: str
    collected_at: datetime
    reachability: str  # online|timeout|error|unknown
    cpu_percent: float | None = None
    memory_percent: float | None = None
    temperature_c: float | None = None
    fan_speed_rpm: int | None = None
    power_status: str | None = None
    interface_summary: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class ServiceResult:
    device_id: str
    observed_at: datetime
    services: list[dict] = field(default_factory=list)  # [{port, protocol, service_name, state}]
    error: str | None = None


class TelemetryCollector:
    """
    Collects CPU, memory, temperature, fans, power and reachability
    by calling adapter.get_health() and adapter.get_interfaces().

    If the device is unreachable (AdapterError / timeout), reachability
    is set accordingly and all other fields remain None.
    """

    def __init__(self, adapter):
        self._adapter = adapter

    def collect(self, device_record) -> TelemetryResult:
        from adapters.base import AdapterError
        from core.models import DiscoveryTarget

        target = DiscoveryTarget(
            name=device_record.name,
            management_ip=device_record.management_ip,
            type=device_record.type,
            credentials_reference_id=device_record.credentials_reference_id,
            vendor=device_record.vendor,
            site=device_record.site,
            port=device_record.management_port or 22,
        )

        collected_at = _utcnow()
        try:
            health: Health = self._adapter.get_health(target)
            try:
                interfaces: list[Interface] = self._adapter.get_interfaces(target)
                total = len(interfaces)
                up = sum(1 for i in interfaces if i.operational_state.lower() == "up")
                down = total - up
                interface_summary = {"total": total, "up": up, "down": down}
            except Exception:
                interface_summary = {}

            # Derive a simple power status string from the health payload
            psu_list = health.power_supplies or []
            if psu_list:
                failed = [p for p in psu_list if p.get("status", "").lower() not in ("ok", "present")]
                power_status = "failed" if failed else "ok"
            else:
                power_status = None

            return TelemetryResult(
                device_id=device_record.id,
                collected_at=collected_at,
                reachability="online",
                cpu_percent=health.cpu_percent,
                memory_percent=health.memory_percent,
                temperature_c=health.temperature_c,
                fan_speed_rpm=health.fan_speed_rpm,
                power_status=power_status,
                interface_summary=interface_summary,
            )
        except AdapterError as exc:
            reason = str(exc)
            reachability = "timeout" if "Timeout" in reason else "error"
            log.warning("telemetry collection failed for %s: %s", device_record.name, reason)
            return TelemetryResult(
                device_id=device_record.id,
                collected_at=collected_at,
                reachability=reachability,
                error=reason,
            )
        except Exception as exc:
            log.exception("unexpected error collecting telemetry for %s", device_record.name)
            return TelemetryResult(
                device_id=device_record.id,
                collected_at=collected_at,
                reachability="error",
                error=str(exc),
            )


class ServiceExposureCollector:
    """
    Detects listening services/ports by parsing Junos system services config.
    This is a config-based check (show system services presence in config),
    not a live port scan — appropriate for managed network devices.

    Returns a list of known-active management services derived from the
    latest stored configuration version text.  When no configuration
    version exists the result has services=[] and error="no_config".
    """

    # Well-known Junos service name → port/protocol mapping
    _SERVICE_MAP = {
        "telnet":      {"port": 23,  "protocol": "tcp"},
        "ftp":         {"port": 21,  "protocol": "tcp"},
        "ssh":         {"port": 22,  "protocol": "tcp"},
        "netconf-ssh": {"port": 830, "protocol": "tcp"},
        "http":        {"port": 80,  "protocol": "tcp"},
        "https":       {"port": 443, "protocol": "tcp"},
        "snmp":        {"port": 161, "protocol": "udp"},
    }

    def __init__(self, configuration_service):
        self._cfg_svc = configuration_service

    def collect(self, device_record, session) -> ServiceResult:
        from sqlalchemy import select
        from database.models import ConfigurationVersionRecord

        observed_at = _utcnow()
        try:
            # Find latest active configuration version for this device
            latest = session.scalar(
                select(ConfigurationVersionRecord)
                .where(
                    ConfigurationVersionRecord.device_id == device_record.id,
                    ConfigurationVersionRecord.retention_state == "active",
                )
                .order_by(ConfigurationVersionRecord.collected_at.desc())
                .limit(1)
            )
            if not latest:
                return ServiceResult(
                    device_id=device_record.id,
                    observed_at=observed_at,
                    error="no_config",
                )

            content: str = self._cfg_svc.content(latest)
            if not content:
                return ServiceResult(
                    device_id=device_record.id,
                    observed_at=observed_at,
                    error="config_content_unavailable",
                )

            services = []
            for svc_name, svc_info in self._SERVICE_MAP.items():
                # Junos set-format: "set system services <service>"
                if f"set system services {svc_name}" in content:
                    services.append({
                        "port": svc_info["port"],
                        "protocol": svc_info["protocol"],
                        "service_name": svc_name,
                        "state": "open",
                    })

            return ServiceResult(
                device_id=device_record.id,
                observed_at=observed_at,
                services=services,
            )
        except Exception as exc:
            log.exception("service exposure collection failed for %s", device_record.name)
            return ServiceResult(
                device_id=device_record.id,
                observed_at=observed_at,
                error=str(exc),
            )
