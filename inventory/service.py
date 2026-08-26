"""Manual device lifecycle: add, edit, delete.

Discovery normally creates devices; this is the operator path for seeding one by hand
before it has ever been reached.  Two boundaries matter here:

* the row stores a **credential reference**, never a secret (blueprint 14.8) — the
  reference names an env/vault profile that :mod:`credentials` resolves at connect time;
* a hand-entered device is unverified, so it starts at ``discovery_state=pending`` with
  confidence 0 and evidence marked ``manual`` instead of inheriting discovered facts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.models import DeviceType
from database.models import (
    AuditLogRecord, ConfigurationVersionRecord, DeviceRecord, InterfaceRecord, NeighborRecord,
)

#: A reference is a profile name, not a credential. The shape alone rules out
#: "user/password" strings, and the forbidden words catch well-meaning misuse.
REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$"
FORBIDDEN_IN_REFERENCE = ("password", "secret", "passphrase", "privatekey", "private_key")


class DeviceInput(BaseModel):
    """Validated Add/Edit Device payload.

    ``extra="forbid"`` is a security control, not a nicety: a client that tries to post a
    ``password`` field is rejected with 422 rather than having it silently ignored.
    """

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    management_ip: str = Field(min_length=1, max_length=45)
    management_port: int = Field(default=22, ge=1, le=65535)
    credentials_reference_id: str = Field(pattern=REFERENCE_PATTERN)
    type: DeviceType = DeviceType.SWITCH
    vendor: str | None = Field(default=None, max_length=100)
    site: str | None = Field(default=None, max_length=255)

    @field_validator("name", "site", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        """Blank input is absent input; a blank name then fails min_length, as it should."""
        return value.strip() if isinstance(value, str) and value.strip() else None

    @field_validator("management_ip")
    @classmethod
    def valid_address(cls, value: str) -> str:
        try:
            return str(ip_address(value.strip()))
        except ValueError as exc:
            raise ValueError("management_ip must be a valid IPv4 or IPv6 address") from exc

    @field_validator("vendor")
    @classmethod
    def normalize_vendor(cls, value: str | None) -> str | None:
        return value.strip().casefold() if isinstance(value, str) and value.strip() else None

    @field_validator("credentials_reference_id")
    @classmethod
    def reference_is_not_a_secret(cls, value: str) -> str:
        if any(word in value.casefold() for word in FORBIDDEN_IN_REFERENCE):
            raise ValueError("credentials_reference_id must name a credential profile, not a secret")
        return value


class DeviceConflict(ValueError):
    """Name, or the management IP + port endpoint, already belongs to another device."""


class InventoryService:
    """Write side of the inventory; the topology and every screen read the same rows."""

    def __init__(self, sessions):
        self.sessions = sessions

    def create(self, payload: DeviceInput, *, actor: str) -> dict:
        with self.sessions() as session:
            self._assert_unique(session, payload)
            record = DeviceRecord(
                id=str(uuid4()), name=payload.name, type=payload.type.value, vendor=payload.vendor,
                model=None, platform=None, os_version=None, serial_number=None,
                management_ip=payload.management_ip, management_port=payload.management_port,
                credentials_reference_id=payload.credentials_reference_id, capabilities=[],
                status="unknown", site=payload.site, discovery_state="pending", last_seen_at=None,
                evidence={"source": "manual", "created_by": actor,
                          "created_at": datetime.now(timezone.utc).isoformat()},
                confidence=0.0,
            )
            session.add(record)
            self._audit(session, actor, "DEVICE_CREATED", record)
            self._commit(session)
            return self.serialize(record)

    def update(self, device_id: str, payload: DeviceInput, *, actor: str) -> dict:
        with self.sessions() as session:
            record = session.get(DeviceRecord, device_id)
            if record is None:
                raise KeyError(device_id)
            self._assert_unique(session, payload, exclude_id=device_id)
            record.name, record.type, record.vendor = payload.name, payload.type.value, payload.vendor
            record.management_ip, record.management_port = payload.management_ip, payload.management_port
            record.credentials_reference_id, record.site = payload.credentials_reference_id, payload.site
            record.evidence = {**(record.evidence or {}), "last_edited_by": actor,
                               "last_edited_at": datetime.now(timezone.utc).isoformat()}
            self._audit(session, actor, "DEVICE_UPDATED", record)
            self._commit(session)
            return self.serialize(record)

    def delete(self, device_id: str, *, actor: str) -> dict:
        """Remove the device and its discovered detail.

        Configuration *artifacts* in object storage are never deleted here, and the audit
        row below records how much version metadata went with the device, so a deletion
        stays explainable afterwards.
        """
        with self.sessions() as session:
            record = session.get(DeviceRecord, device_id)
            if record is None:
                raise KeyError(device_id)
            versions = session.scalar(select(func.count(ConfigurationVersionRecord.id))
                                      .where(ConfigurationVersionRecord.device_id == device_id)) or 0
            summary = {"device": record.name, "management_ip": record.management_ip,
                       "configuration_versions_removed": versions}
            session.add(AuditLogRecord(
                id=str(uuid4()), actor=actor, action="DEVICE_DELETED", resource_type="device",
                resource_id=device_id, correlation_id=device_id, result="SUCCESS",
                created_at=datetime.now(timezone.utc), details=summary))
            session.delete(record)
            session.commit()
            return summary

    def counts(self, device_id: str) -> dict:
        """Interface/neighbor/version counts for the details drawer, metadata only."""
        with self.sessions() as session:
            return {
                "interface_count": session.scalar(select(func.count(InterfaceRecord.id))
                                                  .where(InterfaceRecord.device_id == device_id)) or 0,
                "neighbor_count": session.scalar(select(func.count(NeighborRecord.id))
                                                 .where(NeighborRecord.device_id == device_id)) or 0,
                "configuration_version_count": session.scalar(select(func.count(ConfigurationVersionRecord.id))
                                                              .where(ConfigurationVersionRecord.device_id == device_id)) or 0,
            }

    @staticmethod
    def _assert_unique(session: Session, payload: DeviceInput, exclude_id: str | None = None) -> None:
        """Names are unique; addresses are only unique per port.

        A device is the endpoint it is reached on. Sharing one address across several SSH
        ports is legitimate (a mock lab, a jump host, port-forwarded appliances), so the
        clash is on the pair — matching the ``uq_devices_management_endpoint`` constraint.
        """
        clash = session.scalar(select(DeviceRecord).where(
            (DeviceRecord.name == payload.name)
            | ((DeviceRecord.management_ip == payload.management_ip)
               & (DeviceRecord.management_port == payload.management_port))))
        if clash is not None and clash.id != exclude_id:
            field = "name" if clash.name == payload.name else "management_ip and port"
            raise DeviceConflict(f"another device already uses this {field}")

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except IntegrityError as exc:  # unique constraints are the last word
            session.rollback()
            raise DeviceConflict("name, and the management IP + port pair, must be unique") from exc

    @staticmethod
    def _audit(session: Session, actor: str, action: str, record: DeviceRecord) -> None:
        session.add(AuditLogRecord(
            id=str(uuid4()), actor=actor, action=action, resource_type="device",
            resource_id=record.id, correlation_id=record.id, result="SUCCESS",
            created_at=datetime.now(timezone.utc),
            details={"device": record.name, "management_ip": record.management_ip,
                     "management_port": record.management_port, "type": record.type,
                     "vendor": record.vendor, "site": record.site,
                     "credentials_reference": record.credentials_reference_id}))

    @staticmethod
    def serialize(record: DeviceRecord) -> dict:
        """Inventory row as the UI sees it. The credential reference is a name, not a secret."""
        return {
            "id": record.id, "name": record.name, "type": record.type, "vendor": record.vendor,
            "model": record.model, "platform": record.platform, "os_version": record.os_version,
            "serial_number": record.serial_number, "management_ip": record.management_ip,
            "management_port": record.management_port,
            "credentials_reference_id": record.credentials_reference_id,
            "capabilities": list(record.capabilities or []), "status": record.status,
            "site": record.site, "discovery_state": record.discovery_state,
            "last_seen_at": record.last_seen_at, "confidence": record.confidence,
        }
