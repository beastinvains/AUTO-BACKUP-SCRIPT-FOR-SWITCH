from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class DeviceRecord(Base):
    __tablename__ = "devices"
    # A device is identified by the management endpoint it is reached on, not by address alone:
    # several logical devices can legitimately share one address on different SSH ports (lab
    # estates, jump hosts, port-forwarded appliances). This is the same reasoning that made
    # management_port a persisted column in 0003_device_ssh_port.
    __table_args__ = (UniqueConstraint("management_ip", "management_port", name="uq_devices_management_endpoint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50))
    vendor: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    management_ip: Mapped[str] = mapped_column(String(45), index=True)
    management_port: Mapped[int] = mapped_column(Integer, default=22, server_default="22")
    credentials_reference_id: Mapped[str] = mapped_column(String(255))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50))
    site: Mapped[str | None] = mapped_column(String(255))
    discovery_state: Mapped[str] = mapped_column(String(50))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    interfaces: Mapped[list["InterfaceRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    neighbors: Mapped[list["NeighborRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    health: Mapped["HealthRecord | None"] = relationship(back_populates="device", cascade="all, delete-orphan", uselist=False)
    configuration_versions: Mapped[list["ConfigurationVersionRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class InterfaceRecord(Base):
    __tablename__ = "interfaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    name: Mapped[str] = mapped_column(String(255))
    admin_state: Mapped[str] = mapped_column(String(50))
    operational_state: Mapped[str] = mapped_column(String(50))
    addresses: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    speed: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[DeviceRecord] = relationship(back_populates="interfaces")


class NeighborRecord(Base):
    __tablename__ = "neighbors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    local_interface: Mapped[str] = mapped_column(String(255))
    remote_system_name: Mapped[str | None] = mapped_column(String(255))
    remote_interface: Mapped[str | None] = mapped_column(String(255))
    remote_chassis_id: Mapped[str | None] = mapped_column(String(255))
    device: Mapped[DeviceRecord] = relationship(back_populates="neighbors")


class HealthRecord(Base):
    __tablename__ = "health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), unique=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    memory_percent: Mapped[float | None] = mapped_column(Float)
    uptime: Mapped[str | None] = mapped_column(String(255))
    hardware_status: Mapped[str] = mapped_column(String(50))
    device: Mapped[DeviceRecord] = relationship(back_populates="health")


class ConfigurationVersionRecord(Base):
    __tablename__ = "configuration_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_versions.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_uri: Mapped[str] = mapped_column(String(1024), unique=True)
    source_adapter: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(100))
    parser_version: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    retention_state: Mapped[str] = mapped_column(String(30), default="active")
    device: Mapped[DeviceRecord] = relationship(back_populates="configuration_versions")


class BackupJobRecord(Base):
    __tablename__ = "backup_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requested_by: Mapped[str] = mapped_column(String(255))
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[list] = mapped_column(JSON, default=list)


class ScheduleRecord(Base):
    """A recurring backup window. Execution always goes through BackupService."""

    __tablename__ = "backup_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    device_ids: Mapped[list] = mapped_column(JSON, default=list)  # empty list means every device
    frequency: Mapped[str] = mapped_column(String(20))
    run_at: Mapped[str] = mapped_column(String(5))  # HH:MM, UTC
    day_of_week: Mapped[int | None] = mapped_column(Integer)  # 0=Monday, weekly only
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(30))
    last_job_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(255))
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    result: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
