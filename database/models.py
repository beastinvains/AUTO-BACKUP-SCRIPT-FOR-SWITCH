from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class DeviceRecord(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50))
    vendor: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    management_ip: Mapped[str] = mapped_column(String(45), unique=True)
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

