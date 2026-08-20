from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceType(str, Enum):
    SWITCH = "switch"
    ROUTER = "router"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"
    SERVER = "server"
    HYPERVISOR = "hypervisor"
    VIRTUAL_MACHINE = "virtual_machine"
    OTHER = "other"


class DeviceStatus(str, Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class DiscoveryState(str, Enum):
    PENDING = "pending"
    DISCOVERED = "discovered"
    FAILED = "failed"
    UNRECOGNIZED = "unrecognized"


class Interface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    admin_state: str = "unknown"
    operational_state: str = "unknown"
    addresses: list[str] = Field(default_factory=list)
    description: str | None = None
    speed: str | None = None


class Neighbor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_interface: str
    remote_system_name: str | None = None
    remote_interface: str | None = None
    remote_chassis_id: str | None = None


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    uptime: str | None = None
    hardware_status: str = "unknown"


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=255)
    type: DeviceType = DeviceType.OTHER
    vendor: str | None = None
    model: str | None = None
    platform: str | None = None
    os_version: str | None = None
    serial_number: str | None = None
    management_ip: IPv4Address | IPv6Address
    credentials_reference_id: str = Field(min_length=1, max_length=255)
    capabilities: list[str] = Field(default_factory=list)
    status: DeviceStatus = DeviceStatus.UNKNOWN
    site: str | None = None
    discovery_state: DiscoveryState = DiscoveryState.PENDING
    last_seen_at: datetime | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("vendor", "platform", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return value.lower().strip() if isinstance(value, str) and value.strip() else None


class DiscoveryTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    management_ip: IPv4Address | IPv6Address
    credentials_reference_id: str = Field(min_length=1)
    type: DeviceType = DeviceType.OTHER
    vendor: str | None = None
    site: str | None = None
    port: int = Field(default=22, ge=1, le=65535)


class DiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device: Device
    interfaces: list[Interface] = Field(default_factory=list)
    neighbors: list[Neighbor] = Field(default_factory=list)
    health: Health = Field(default_factory=Health)

