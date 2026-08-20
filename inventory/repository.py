from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from core.models import Device, DiscoveryResult, Health, Interface, Neighbor
from database.models import DeviceRecord, HealthRecord, InterfaceRecord, NeighborRecord


class InventoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, result: DiscoveryResult) -> Device:
        device = result.device
        record = self.session.scalar(select(DeviceRecord).where(DeviceRecord.management_ip == str(device.management_ip)))
        values = device.model_dump(mode="python")
        values.pop("id")
        values["management_ip"] = str(values["management_ip"])
        if record is None:
            record = DeviceRecord(id=str(device.id), **values)
            self.session.add(record)
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(record, key, value)
            record.interfaces.clear()
            record.neighbors.clear()
            record.health = None
        record.interfaces = [InterfaceRecord(**item.model_dump()) for item in result.interfaces]
        record.neighbors = [NeighborRecord(**item.model_dump()) for item in result.neighbors]
        record.health = HealthRecord(**result.health.model_dump())
        self.session.commit()
        self.session.refresh(record)
        return self._device(record)

    def get(self, device_id: str) -> DeviceRecord | None:
        return self.session.scalar(select(DeviceRecord).options(
            selectinload(DeviceRecord.interfaces), selectinload(DeviceRecord.neighbors), selectinload(DeviceRecord.health)
        ).where(DeviceRecord.id == device_id))

    def list(self) -> list[DeviceRecord]:
        return list(self.session.scalars(select(DeviceRecord).order_by(DeviceRecord.name)))

    @staticmethod
    def _device(record: DeviceRecord) -> Device:
        return Device.model_validate({
            "id": record.id, "name": record.name, "type": record.type, "vendor": record.vendor,
            "model": record.model, "platform": record.platform, "os_version": record.os_version,
            "serial_number": record.serial_number, "management_ip": record.management_ip,
            "credentials_reference_id": record.credentials_reference_id, "capabilities": record.capabilities,
            "status": record.status, "site": record.site, "discovery_state": record.discovery_state,
            "last_seen_at": record.last_seen_at, "evidence": record.evidence, "confidence": record.confidence,
        })
