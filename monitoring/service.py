"""
Phase 4 — Monitoring Service.

Orchestrates fan-out collection across all (or selected) devices,
persists MonitoringJobRecord, TelemetryRecord, and ServiceObservationRecord,
and feeds results into EvidenceService.

Isolation guarantee: a failure for device N does not abort collection
for device N+1; errors are recorded per-device and the job completes
with status="partial" if some devices failed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    DeviceRecord,
    MonitoringJobRecord,
    ServiceObservationRecord,
    TelemetryRecord,
)
from monitoring.collectors import ServiceExposureCollector, TelemetryCollector

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringService:
    """
    Runs telemetry and/or service-exposure collection for a set of devices.

    Pass ``kind="telemetry"`` for fast health polling (every 5 min),
    ``kind="service"`` for slow security scans (every 30 min), or
    ``kind="all"`` to run both in one job.
    """

    def __init__(
        self,
        session_factory,
        adapter,
        configuration_service,
        evidence_service=None,
        alerts_service=None,
    ):
        self._session_factory = session_factory
        self._telemetry_collector = TelemetryCollector(adapter)
        self._service_collector = ServiceExposureCollector(configuration_service)
        self._evidence = evidence_service
        self._alerts = alerts_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_collection(
        self,
        kind: str = "telemetry",
        device_ids: list[str] | None = None,
        triggered_by: str = "manual",
        interval_seconds: int | None = None,
    ) -> dict:
        """
        Create a MonitoringJob, collect from all matching devices, persist results.
        Returns a serialized job summary dict.
        """
        job_id = str(uuid4())
        now = _utcnow()

        with self._session_factory() as session:
            job = MonitoringJobRecord(
                id=job_id,
                status="running",
                kind=kind,
                device_ids=device_ids or [],
                created_at=now,
                started_at=now,
                triggered_by=triggered_by,
                collection_interval_seconds=interval_seconds,
            )
            session.add(job)
            session.commit()

        # Resolve target devices
        with self._session_factory() as session:
            q = select(DeviceRecord)
            if device_ids:
                q = q.where(DeviceRecord.id.in_(device_ids))
            devices = list(session.scalars(q))

        success = 0
        errors = 0
        for device in devices:
            try:
                if kind in ("telemetry", "all"):
                    self._collect_telemetry(device, job_id)
                if kind in ("service", "all"):
                    self._collect_services(device, job_id)
                success += 1
            except Exception:
                log.exception("collection loop error for device %s", device.id)
                errors += 1

        final_status = "success" if errors == 0 else ("failed" if success == 0 else "partial")
        with self._session_factory() as session:
            job_rec = session.get(MonitoringJobRecord, job_id)
            if job_rec:
                job_rec.status = final_status
                job_rec.completed_at = _utcnow()
                job_rec.success_count = success
                job_rec.error_count = errors
                session.commit()

        return self._serialize_job(job_id)

    def get_latest_telemetry(self, device_id: str) -> dict | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(TelemetryRecord)
                .where(TelemetryRecord.device_id == device_id)
                .order_by(TelemetryRecord.collected_at.desc())
                .limit(1)
            )
            return self._serialize_telemetry(record) if record else None

    def get_telemetry_history(
        self,
        device_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        with self._session_factory() as session:
            q = select(TelemetryRecord).where(TelemetryRecord.device_id == device_id)
            if start:
                q = q.where(TelemetryRecord.collected_at >= start)
            if end:
                q = q.where(TelemetryRecord.collected_at <= end)
            q = q.order_by(TelemetryRecord.collected_at.desc()).limit(limit)
            return [self._serialize_telemetry(r) for r in session.scalars(q)]

    def get_service_observations(self, device_id: str, limit: int = 50) -> list[dict]:
        with self._session_factory() as session:
            q = (
                select(ServiceObservationRecord)
                .where(ServiceObservationRecord.device_id == device_id)
                .order_by(ServiceObservationRecord.observed_at.desc())
                .limit(limit)
            )
            return [self._serialize_service(r) for r in session.scalars(q)]

    def get_monitoring_overview(self) -> dict:
        """Estate-wide monitoring coverage summary."""
        with self._session_factory() as session:
            devices = list(session.scalars(select(DeviceRecord)))
            coverage = []
            for dev in devices:
                latest = session.scalar(
                    select(TelemetryRecord)
                    .where(TelemetryRecord.device_id == dev.id)
                    .order_by(TelemetryRecord.collected_at.desc())
                    .limit(1)
                )
                coverage.append({
                    "device_id": dev.id,
                    "device_name": dev.name,
                    "device_status": dev.status,
                    "last_collected_at": latest.collected_at if latest else None,
                    "reachability": latest.reachability if latest else "not_collected",
                    "cpu_percent": latest.cpu_percent if latest else None,
                    "memory_percent": latest.memory_percent if latest else None,
                    "temperature_c": latest.temperature_c if latest else None,
                    "fan_speed_rpm": latest.fan_speed_rpm if latest else None,
                    "power_status": latest.power_status if latest else None,
                })
            online = sum(1 for c in coverage if c["reachability"] == "online")
            return {
                "total_devices": len(devices),
                "devices_online": online,
                "devices_offline": len(devices) - online,
                "devices_not_collected": sum(1 for c in coverage if c["reachability"] == "not_collected"),
                "coverage": coverage,
            }

    def get_job(self, job_id: str) -> dict | None:
        return self._serialize_job(job_id)

    # ------------------------------------------------------------------
    # Internal collection helpers
    # ------------------------------------------------------------------

    def _collect_telemetry(self, device: DeviceRecord, job_id: str):
        result = self._telemetry_collector.collect(device)

        with self._session_factory() as session:
            record = TelemetryRecord(
                id=str(uuid4()),
                device_id=result.device_id,
                collection_job_id=job_id,
                collected_at=result.collected_at,
                cpu_percent=result.cpu_percent,
                memory_percent=result.memory_percent,
                temperature_c=result.temperature_c,
                fan_speed_rpm=result.fan_speed_rpm,
                power_status=result.power_status,
                reachability=result.reachability,
                interface_summary=result.interface_summary,
            )
            session.add(record)
            session.commit()

        # Emit an alert if the device became unreachable
        if result.reachability != "online" and self._alerts:
            try:
                self._alerts.emit_alert(
                    category="device_unreachable",
                    device_id=device.id,
                    severity="high",
                    title=f"{device.name} is {result.reachability}",
                    message=result.error or "Device did not respond to monitoring collection.",
                    actor="monitoring",
                )
            except Exception:
                log.exception("failed to emit unreachable alert for %s", device.id)

    def _collect_services(self, device: DeviceRecord, job_id: str):
        with self._session_factory() as session:
            result = self._service_collector.collect(device, session)

        if result.error:
            log.warning("service collection skipped for %s: %s", device.name, result.error)
            return

        now = result.observed_at
        with self._session_factory() as session:
            for svc in result.services:
                record = ServiceObservationRecord(
                    id=str(uuid4()),
                    device_id=result.device_id,
                    collection_job_id=job_id,
                    observed_at=now,
                    port=svc["port"],
                    protocol=svc["protocol"],
                    service_name=svc.get("service_name"),
                    state=svc.get("state", "unknown"),
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(record)
            session.commit()

    # ------------------------------------------------------------------
    # Serializers
    # ------------------------------------------------------------------

    def _serialize_job(self, job_id: str) -> dict | None:
        with self._session_factory() as session:
            job = session.get(MonitoringJobRecord, job_id)
            if not job:
                return None
            return {
                "id": job.id,
                "status": job.status,
                "kind": job.kind,
                "device_ids": job.device_ids,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "triggered_by": job.triggered_by,
                "collection_interval_seconds": job.collection_interval_seconds,
                "success_count": job.success_count,
                "error_count": job.error_count,
            }

    @staticmethod
    def _serialize_telemetry(record: TelemetryRecord) -> dict:
        return {
            "id": record.id,
            "device_id": record.device_id,
            "collection_job_id": record.collection_job_id,
            "collected_at": record.collected_at,
            "cpu_percent": record.cpu_percent,
            "memory_percent": record.memory_percent,
            "temperature_c": record.temperature_c,
            "fan_speed_rpm": record.fan_speed_rpm,
            "power_status": record.power_status,
            "reachability": record.reachability,
            "interface_summary": record.interface_summary,
        }

    @staticmethod
    def _serialize_service(record: ServiceObservationRecord) -> dict:
        return {
            "id": record.id,
            "device_id": record.device_id,
            "observed_at": record.observed_at,
            "port": record.port,
            "protocol": record.protocol,
            "service_name": record.service_name,
            "state": record.state,
            "first_seen_at": record.first_seen_at,
            "last_seen_at": record.last_seen_at,
        }
