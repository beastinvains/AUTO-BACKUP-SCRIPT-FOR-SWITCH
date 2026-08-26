"""Identity correlation for topology nodes.

LLDP tells one device what its neighbor *calls itself*, which is rarely the exact
string stored in inventory: a neighbor may be reported as ``core-sw01``,
``core-sw01.example.local``, ``10.10.10.10`` or only as a chassis MAC.  This module
turns those observations into inventory device ids **when the evidence is
unambiguous**, and refuses to guess otherwise (blueprint 14.3: discovery produces
evidence, not unquestioned facts).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from ipaddress import ip_address

_HEX_MAC = re.compile(r"^[0-9a-f]{12}$")
_SEPARATORS = re.compile(r"[:\-.\s]")


def normalize_hostname(value: object) -> str | None:
    """Casefold a hostname and drop the trailing FQDN dot; ``None`` when unusable."""
    text = str(value or "").strip().rstrip(".").casefold()
    return text or None


def short_hostname(value: object) -> str | None:
    """Return the leftmost DNS label so ``core-sw01.example.local`` matches ``core-sw01``."""
    hostname = normalize_hostname(value)
    return hostname.split(".", 1)[0] if hostname else None


def normalize_chassis_id(value: object) -> str | None:
    """Canonicalize a chassis id so ``00:11:22:33:44:55`` equals ``0011.2233.4455``."""
    text = str(value or "").strip().casefold()
    if not text:
        return None
    stripped = _SEPARATORS.sub("", text)
    return stripped if _HEX_MAC.match(stripped) else text


def normalize_ip(value: object) -> str | None:
    """Return a canonical IP string, or ``None`` when the value is not an address."""
    text = str(value or "").strip()
    try:
        return str(ip_address(text))
    except ValueError:
        return None


@dataclass(frozen=True)
class DeviceFacts:
    """Storage-independent view of one managed device, built from inventory."""

    id: str
    name: str
    type: str = "other"
    vendor: str | None = None
    model: str | None = None
    platform: str | None = None
    os_version: str | None = None
    management_ip: str | None = None
    serial_number: str | None = None
    status: str = "unknown"
    site: str | None = None
    discovery_state: str = "pending"
    last_seen_at: datetime | None = None
    confidence: float = 0.0
    interface_count: int = 0
    neighbor_count: int = 0
    last_backup_at: datetime | None = None


@dataclass(frozen=True)
class NeighborFacts:
    """One LLDP observation reported by ``device_id``."""

    device_id: str
    local_interface: str | None
    remote_system_name: str | None = None
    remote_interface: str | None = None
    remote_chassis_id: str | None = None


@dataclass
class DeviceIndex:
    """Alias table used to resolve a neighbor report to an inventory device id.

    An alias that points at more than one device is ambiguous and is removed rather
    than resolved: two devices sharing a short hostname must not be silently merged.
    """

    aliases: dict[str, str] = field(default_factory=dict)
    ambiguous: set[str] = field(default_factory=set)

    @classmethod
    def build(cls, devices: list[DeviceFacts]) -> "DeviceIndex":
        index = cls()
        for device in devices:
            for alias in cls._aliases_for(device):
                index._add(alias, device.id)
        return index

    @staticmethod
    def _aliases_for(device: DeviceFacts) -> set[str]:
        """Every identity string this device may legitimately be reported as."""
        candidates = {
            normalize_hostname(device.name),
            short_hostname(device.name),
            normalize_ip(device.management_ip),
            normalize_chassis_id(device.serial_number),
        }
        return {alias for alias in candidates if alias}

    def _add(self, alias: str, device_id: str) -> None:
        existing = self.aliases.get(alias)
        if existing is None and alias not in self.ambiguous:
            self.aliases[alias] = device_id
        elif existing is not None and existing != device_id:
            del self.aliases[alias]
            self.ambiguous.add(alias)

    def resolve(self, *candidates: str | None) -> str | None:
        """Return the single device id matching any candidate alias, else ``None``."""
        for candidate in candidates:
            if candidate and (device_id := self.aliases.get(candidate)):
                return device_id
        return None

    def resolve_neighbor(self, neighbor: NeighborFacts) -> str | None:
        """Correlate one LLDP report using hostname, management IP, then chassis id."""
        return self.resolve(*self.candidates(neighbor))

    @staticmethod
    def candidates(neighbor: NeighborFacts) -> list[str]:
        """Identity strings this report could match, in decreasing order of specificity."""
        name = neighbor.remote_system_name
        candidates = (
            normalize_hostname(name),
            short_hostname(name),
            normalize_ip(name),
            normalize_chassis_id(neighbor.remote_chassis_id),
        )
        return [candidate for candidate in candidates if candidate]

    def ambiguous_matches(self, neighbor: NeighborFacts) -> set[str]:
        """Aliases in this report that point at more than one device.

        Only these are worth surfacing: an alias two devices happen to share is harmless
        until something actually reports it, and listing unreported collisions would put a
        warning on the map for a link nobody claimed.
        """
        return {candidate for candidate in self.candidates(neighbor) if candidate in self.ambiguous}


def external_node_key(neighbor: NeighborFacts) -> str | None:
    """Stable id for a neighbor that is not in inventory.

    Chassis id wins over the advertised name because it is the more stable
    identifier, so the same unmanaged neighbor seen from two switches collapses into
    one node instead of two.
    """
    chassis = normalize_chassis_id(neighbor.remote_chassis_id)
    if chassis:
        return f"external:chassis:{chassis}"
    hostname = normalize_hostname(neighbor.remote_system_name)
    return f"external:name:{hostname}" if hostname else None
