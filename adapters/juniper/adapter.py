from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Callable, Iterator

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from adapters.base import AdapterError, BaseDeviceAdapter
from core.models import (
    Device, DeviceStatus, DeviceType, DiscoveryResult, DiscoveryState,
    DiscoveryTarget, Health, Interface, Neighbor, utcnow,
)
from credentials import get_credentials

COMMANDS = {
    "facts": "show version | no-more",
    "interfaces": "show interfaces terse | no-more",
    "descriptions": "show interfaces descriptions | no-more",
    "neighbors": "show lldp neighbors | no-more",
    "health": "show system processes extensive | no-more",
}
_ALLOWED_COMMANDS = frozenset(COMMANDS.values())


def _first(pattern: str, output: str) -> str | None:
    match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_device_info(output: str, target: DiscoveryTarget) -> Device:
    hostname = _first(r"^Hostname:\s*(.+)$", output) or target.name
    model = _first(r"^Model:\s*(.+)$", output)
    version = _first(r"^Junos:\s*(.+)$", output)
    serial = _first(r"^System serial number:\s*(.+)$", output)
    uptime = _first(r"^System uptime:\s*(.+)$", output)
    recognized = bool(version or re.search(r"\bJunos\b", output, re.IGNORECASE))
    return Device(
        name=hostname, type=target.type if target.type != DeviceType.OTHER else DeviceType.SWITCH,
        vendor="juniper" if recognized else None, model=model, platform="junos" if recognized else None,
        os_version=version, serial_number=serial, management_ip=target.management_ip,
        credentials_reference_id=target.credentials_reference_id, capabilities=[
            "device_info", "health", "interfaces", "lldp_neighbors"
        ] if recognized else [], status=DeviceStatus.ONLINE if recognized else DeviceStatus.UNKNOWN,
        site=target.site, discovery_state=DiscoveryState.DISCOVERED if recognized else DiscoveryState.UNRECOGNIZED,
        last_seen_at=utcnow(), evidence={"fingerprint": "show version", "uptime": uptime},
        confidence=0.95 if recognized else 0.2,
    )


def parse_interfaces(terse: str, descriptions: str = "") -> list[Interface]:
    descriptions_by_name = {}
    for line in descriptions.splitlines():
        parts = line.split(None, 3)
        if len(parts) >= 4 and re.match(r"^(?:[a-z]{2}-|irb\.)", parts[0], re.I):
            descriptions_by_name[parts[0]] = parts[3]
    results = []
    for line in terse.splitlines():
        parts = line.split()
        if len(parts) < 3 or not re.match(r"^(?:[a-z]{2}-|irb\.)", parts[0], re.I):
            continue
        name, admin, oper = parts[:3]
        addresses = [value for value in parts[3:] if "/" in value]
        results.append(Interface(
            name=name, admin_state=admin.lower(), operational_state=oper.lower(),
            addresses=addresses, description=descriptions_by_name.get(name)
        ))
    return results


def parse_neighbors(output: str) -> list[Neighbor]:
    results = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3 or not re.match(r"^[a-z]{2}-", parts[0], re.I):
            continue
        # Standard Junos output includes: local, parent, chassis ID, port, system name.
        if len(parts) >= 5:
            results.append(Neighbor(
                local_interface=parts[0], remote_chassis_id=parts[2],
                remote_interface=parts[3], remote_system_name=" ".join(parts[4:]),
            ))
        else:
            results.append(Neighbor(
                local_interface=parts[0], remote_chassis_id=parts[1],
                remote_system_name=parts[2], remote_interface=" ".join(parts[3:]) or None,
            ))
    return results


def parse_health(output: str, uptime: str | None = None) -> Health:
    cpu = _first(r"CPU utilization:\s*(\d+(?:\.\d+)?)", output)
    memory = _first(r"Memory utilization:\s*(\d+(?:\.\d+)?)", output)
    hardware = "ok" if "error" not in output.lower() else "warning"
    return Health(cpu_percent=float(cpu) if cpu else None, memory_percent=float(memory) if memory else None,
                  uptime=uptime, hardware_status=hardware)


class JuniperAdapter(BaseDeviceAdapter):
    def __init__(self, credentials_provider: Callable[[str], dict[str, str]] | None = None,
                 connection_factory=ConnectHandler, timeout: int = 20, command_timeout: int = 30):
        self.credentials_provider = credentials_provider or get_credentials
        self.connection_factory = connection_factory
        self.timeout = timeout
        self.command_timeout = command_timeout

    @contextmanager
    def _connection(self, target: DiscoveryTarget) -> Iterator[object]:
        credentials = self.credentials_provider(target.credentials_reference_id)
        try:
            connection = self.connection_factory(
                device_type="juniper_junos", host=str(target.management_ip), port=target.port,
                username=credentials["username"], password=credentials["password"],
                timeout=self.timeout, banner_timeout=self.timeout,
            )
            yield connection
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            raise AdapterError(exc.__class__.__name__) from exc
        except Exception as exc:
            raise AdapterError("connection_error") from exc
        finally:
            if "connection" in locals():
                try:
                    connection.disconnect()
                except Exception:
                    pass

    def _run(self, connection: object, key: str) -> str:
        command = COMMANDS[key]
        if command not in _ALLOWED_COMMANDS:
            raise AdapterError("command_not_allowlisted")
        try:
            return connection.send_command(command, read_timeout=self.command_timeout)
        except Exception as exc:
            raise AdapterError("command_error") from exc

    def discover(self, target: DiscoveryTarget) -> DiscoveryResult:
        with self._connection(target) as connection:
            facts = self._run(connection, "facts")
            device = parse_device_info(facts, target)
            if device.discovery_state == DiscoveryState.UNRECOGNIZED:
                return DiscoveryResult(device=device)
            interface_output = self._run(connection, "interfaces")
            descriptions = self._run(connection, "descriptions")
            neighbor_output = self._run(connection, "neighbors")
            health_output = self._run(connection, "health")
        return DiscoveryResult(
            device=device, interfaces=parse_interfaces(interface_output, descriptions),
            neighbors=parse_neighbors(neighbor_output),
            health=parse_health(health_output, device.evidence.get("uptime")),
        )

    def get_device_info(self, target: DiscoveryTarget):
        with self._connection(target) as connection:
            return parse_device_info(self._run(connection, "facts"), target)

    def get_health(self, target: DiscoveryTarget):
        with self._connection(target) as connection:
            return parse_health(self._run(connection, "health"))

    def get_interfaces(self, target: DiscoveryTarget):
        with self._connection(target) as connection:
            return parse_interfaces(self._run(connection, "interfaces"), self._run(connection, "descriptions"))

    def get_neighbors(self, target: DiscoveryTarget):
        with self._connection(target) as connection:
            return parse_neighbors(self._run(connection, "neighbors"))
