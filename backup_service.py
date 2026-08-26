"""Backup job orchestration; API, scheduler, and compatibility callers share this path."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import select

from adapters.base import AdapterError, BaseDeviceAdapter
from audit.logging import log_discovery
from configuration.service import ConfigurationService
from core.models import DiscoveryTarget
from database.models import AuditLogRecord, BackupJobRecord, DeviceRecord


class BackupJobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class BackupService:
    """One execution path for API, scheduler, and legacy CLI callers."""
    def __init__(self, adapter: BaseDeviceAdapter, sessions, configurations: ConfigurationService, logger=None):
        self.adapter, self.sessions, self.configurations, self.logger = adapter, sessions, configurations, logger

    def create_job(self, device_ids: list[str] | None, *, requested_by: str) -> str:
        with self.sessions() as session:
            selected = list(session.scalars(select(DeviceRecord).where(DeviceRecord.id.in_(device_ids)))) if device_ids else list(session.scalars(select(DeviceRecord)))
            if device_ids and len(selected) != len(set(device_ids)):
                raise ValueError("one or more devices are outside the authorized inventory scope")
            job = BackupJobRecord(id=str(uuid4()), requested_by=requested_by, target_scope=[item.id for item in selected], created_at=datetime.now(timezone.utc), status=BackupJobStatus.PENDING.value, success_count=0, failure_count=0, results=[])
            session.add(job); session.commit()
            return job.id

    def run(self, job_id: str) -> dict:
        with self.sessions() as session:
            job = session.get(BackupJobRecord, job_id)
            if not job: raise KeyError(job_id)
            job.status, job.started_at = BackupJobStatus.RUNNING.value, datetime.now(timezone.utc)
            devices = list(session.scalars(select(DeviceRecord).where(DeviceRecord.id.in_(job.target_scope))))
            session.commit()
        results = [self._backup_one(job_id, device.id) for device in devices]
        with self.sessions() as session:
            job = session.get(BackupJobRecord, job_id)
            job.results, job.success_count = results, sum(item["status"] == "SUCCESS" for item in results)
            job.failure_count, job.completed_at = len(results) - job.success_count, datetime.now(timezone.utc)
            job.status = BackupJobStatus.SUCCESS.value if not job.failure_count else BackupJobStatus.FAILED.value if not job.success_count else BackupJobStatus.PARTIAL.value
            session.commit()
            return self.serialize_job(job)

    def _backup_one(self, job_id: str, device_id: str) -> dict:
        started = datetime.now(timezone.utc)
        with self.sessions() as session:
            device = session.get(DeviceRecord, device_id)
            job = session.get(BackupJobRecord, job_id)
            target = DiscoveryTarget(name=device.name, management_ip=device.management_ip, port=device.management_port, credentials_reference_id=device.credentials_reference_id, site=device.site)
            try:
                raw = self.adapter.get_configuration(target)
                stored = self.configurations.store(session, device_id=device.id, device_name=device.name, raw=raw, source_adapter=self.adapter.__class__.__name__, platform=device.platform or "junos")
                result = {"device_id": device.id, "device": device.name, "status": "SUCCESS", "version_id": stored.version.id, "sha256": stored.version.sha256, "change_status": "CONFIGURATION_CHANGED" if stored.changed else "NO_CHANGE", "duration_seconds": round((datetime.now(timezone.utc)-started).total_seconds(), 3)}
                self._audit(session, job_id, device.id, "SUCCESS", result, job.requested_by); session.commit(); return result
            except AdapterError as exc: category = str(exc)
            except Exception:
                category = "collection_error"
                if self.logger: log_discovery(self.logger, event="backup_failed", device_id=device_id, error=category)
            result = {"device_id": device.id, "device": device.name, "status": "FAILED", "error_category": category, "duration_seconds": round((datetime.now(timezone.utc)-started).total_seconds(), 3)}
            self._audit(session, job_id, device.id, "FAILED", result, job.requested_by); session.commit(); return result

    @staticmethod
    def _audit(session, job_id: str, device_id: str, result: str, details: dict, actor: str) -> None:
        session.add(AuditLogRecord(id=str(uuid4()), actor=actor, action="BACKUP_CONFIGURATION", resource_type="device", resource_id=device_id, correlation_id=job_id, result=result, created_at=datetime.now(timezone.utc), details={k: v for k, v in details.items() if k not in {"raw", "configuration"}}))

    @staticmethod
    def serialize_job(job: BackupJobRecord) -> dict:
        return {"job_id": job.id, "requested_by": job.requested_by, "target_scope": job.target_scope, "created_at": job.created_at, "started_at": job.started_at, "completed_at": job.completed_at, "status": job.status, "success_count": job.success_count, "failure_count": job.failure_count, "results": job.results}
