from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from adapters.base import AdapterError, BaseDeviceAdapter
from audit.logging import get_discovery_logger, log_discovery
from core.models import DiscoveryResult, DiscoveryTarget
from database.models import AuditLogRecord
from inventory.repository import InventoryRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class DeviceJobResult(BaseModel):
    target: str
    status: JobStatus
    device_id: UUID | None = None
    error: str | None = None


class DiscoveryJob(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    results: list[DeviceJobResult] = Field(default_factory=list)


class DiscoveryService:
    def __init__(self, adapter: BaseDeviceAdapter, repository_factory):
        self.adapter = adapter
        self.repository_factory = repository_factory
        self.jobs: dict[UUID, DiscoveryJob] = {}
        self.logger = get_discovery_logger()

    def run(self, targets: list[DiscoveryTarget]) -> DiscoveryJob:
        job = DiscoveryJob()
        self.jobs[job.job_id] = job
        job.status, job.started_at = JobStatus.RUNNING, utcnow()
        for target in targets:
            started = perf_counter()
            try:
                result: DiscoveryResult = self.adapter.discover(target)
                with self.repository_factory() as session:
                    device = InventoryRepository(session).upsert(result)
                job.results.append(DeviceJobResult(target=target.name, status=JobStatus.SUCCESS, device_id=device.id))
                duration = round((perf_counter()-started)*1000)
                log_discovery(self.logger, job_id=job.job_id, device=target.name, event="discovery_complete",
                              status="success", duration_ms=duration)
                self._record_event(job.job_id, target.name, "SUCCESS", resource_id=str(device.id), duration_ms=duration)
            except AdapterError as exc:
                job.results.append(DeviceJobResult(target=target.name, status=JobStatus.FAILED, error=str(exc)))
                duration = round((perf_counter()-started)*1000)
                log_discovery(self.logger, job_id=job.job_id, device=target.name, event="discovery_complete",
                              status="failed", error_category=str(exc), duration_ms=duration)
                self._record_event(job.job_id, target.name, "FAILED", error_category=str(exc), duration_ms=duration)
        successes = sum(item.status == JobStatus.SUCCESS for item in job.results)
        job.status = JobStatus.SUCCESS if successes == len(targets) else (JobStatus.PARTIAL if successes else JobStatus.FAILED)
        job.completed_at = utcnow()
        return job

    def _record_event(self, job_id, target: str, result: str, *, resource_id: str | None = None,
                      error_category: str | None = None, duration_ms: int | None = None) -> None:
        """Persist the outcome so the Logs screen survives a restart. Never fails a job."""
        details = {"target": target, "duration_ms": duration_ms}
        if error_category:
            details["error_category"] = error_category
        try:
            with self.repository_factory() as session:
                session.add(AuditLogRecord(
                    id=str(uuid4()), actor="discovery", action="DEVICE_DISCOVERY", resource_type="device",
                    resource_id=resource_id or target, correlation_id=str(job_id), result=result,
                    created_at=utcnow(), details=details))
                session.commit()
        except Exception as exc:  # auditing must not break discovery itself
            log_discovery(self.logger, event="audit_write_failed", error=type(exc).__name__)

