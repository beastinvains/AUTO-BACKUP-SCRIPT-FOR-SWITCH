from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from adapters.juniper.adapter import JuniperAdapter
from audit.query import CATEGORIES, STATUSES, query_events
from backend.dashboard import build_summary
from core.models import DiscoveryTarget
from database.models import Base
from database.models import AuditLogRecord, BackupJobRecord, ConfigurationVersionRecord, DeviceRecord
from database.session import SessionLocal, engine
from discovery.jobs import DiscoveryService
from inventory.repository import InventoryRepository
from inventory.service import DeviceConflict, DeviceInput, InventoryService
from backup_service import BackupService
from configuration.service import ConfigurationService, configuration_diff
from config import load_config
from schedule_service import ScheduleService, ScheduleSpec
from scheduler import ScheduleRunner
from storage.local import LocalArtifactStorage
from topology.service import TopologyService


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Nothing runs until an operator creates a schedule, so starting the clock here is
    # inert on a fresh database and keeps one scheduler in one place.
    schedule_runner.start()
    try:
        yield
    finally:
        schedule_runner.stop()


app = FastAPI(title="Infrastructure Vision Platform - Phase 3", lifespan=lifespan)
# The React (Vite) client runs on http://localhost:5173 in development. The dev
# server also proxies /api, so this is a belt-and-suspenders allowance and lets a
# production build call the API directly. X-Role/X-Actor are covered by "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
service = DiscoveryService(JuniperAdapter(), SessionLocal)
backup_service = BackupService(JuniperAdapter(), SessionLocal, ConfigurationService(LocalArtifactStorage(load_config().backup_root)))
topology_service = TopologyService(SessionLocal)
inventory_service = InventoryService(SessionLocal)
schedule_service = ScheduleService(SessionLocal, backup_service)
schedule_runner = ScheduleRunner(schedule_service)


def run_scheduled_backup() -> dict:
    """Scheduler callback: deliberately uses the identical job/service path as POST."""
    job_id = backup_service.create_job(None, requested_by="scheduler")
    return backup_service.run(job_id)


def get_session():
    with SessionLocal() as session:
        yield session


def require_backup_operator(x_role: str | None = Header(default=None), x_actor: str | None = Header(default=None)) -> str:
    """Small Phase-2 authorization seam; identity integration belongs to Phase 0's identity module."""
    if x_role not in {"admin", "operator"}:
        raise HTTPException(403, "backup operator role required")
    return x_actor or "unknown"


def require_admin(x_role: str | None = Header(default=None), x_actor: str | None = Header(default=None)) -> str:
    """Inventory and schedule changes are administrative; a read-only role cannot reach them."""
    if x_role != "admin":
        raise HTTPException(403, "administrator role required")
    return x_actor or "unknown"


class BackupRequest(BaseModel):
    device_ids: list[str] = Field(default_factory=list)


def topology_filters(site: str | None = None, vendor: str | None = None,
                     device_type: str | None = None, status: str | None = None) -> dict:
    """Query filters shared by every topology route (Phase 3 section 12)."""
    return {"site": site, "vendor": vendor, "device_type": device_type, "status": status}


@app.post("/api/discovery/jobs")
def create_discovery_job(targets: list[DiscoveryTarget]):
    return service.run(targets)


@app.get("/api/discovery/jobs/{job_id}")
def get_job(job_id: UUID):
    job = service.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Discovery job not found")
    return job


@app.get("/api/devices")
def list_devices(session: Session = Depends(get_session)):
    return [InventoryRepository._device(item) for item in InventoryRepository(session).list()]


@app.get("/api/devices/{device_id}")
def get_device(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    return InventoryRepository._device(record)


@app.get("/api/devices/{device_id}/interfaces")
def get_interfaces(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    return record.interfaces


@app.get("/api/devices/{device_id}/neighbors")
def get_neighbors(device_id: str, resolved: bool = False, session: Session = Depends(get_session)):
    """Raw LLDP neighbours by default; ``resolved=true`` adds the correlated device id."""
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    if resolved:
        return topology_service.neighbors(device_id)
    return record.neighbors


@app.get("/api/devices/{device_id}/health")
def get_health(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record or not record.health:
        raise HTTPException(404, "Health record not found")
    return record.health


@app.get("/api/backups")
def list_backups(session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    return [BackupService.serialize_job(item) for item in session.scalars(select(BackupJobRecord).order_by(BackupJobRecord.created_at.desc()))]


@app.post("/api/backups", status_code=202)
def create_backup(request: BackupRequest, background: BackgroundTasks, actor: str = Depends(require_backup_operator)):
    try:
        job_id = backup_service.create_job(request.device_ids or None, requested_by=actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    background.add_task(backup_service.run, job_id)
    return {"job_id": job_id, "status": "PENDING"}


@app.get("/api/backups/{job_id}")
def get_backup(job_id: str, session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    job = session.get(BackupJobRecord, job_id)
    if not job: raise HTTPException(404, "Backup job not found")
    return BackupService.serialize_job(job)


@app.get("/api/devices/{device_id}/configurations")
def list_configurations(device_id: str, session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    if not session.get(DeviceRecord, device_id):
        raise HTTPException(404, "Device not found")
    records = session.scalars(select(ConfigurationVersionRecord).where(ConfigurationVersionRecord.device_id == device_id).order_by(ConfigurationVersionRecord.collected_at.desc())).all()
    return [{"version_id": x.id, "parent_version_id": x.parent_version_id, "timestamp": x.collected_at, "sha256": x.sha256,
             "size_bytes": x.size_bytes, "status": x.status, "retention_state": x.retention_state} for x in records]


@app.get("/api/devices/{device_id}/configurations/{version_id}")
def get_configuration(device_id: str, version_id: str, session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    record = session.get(ConfigurationVersionRecord, version_id)
    if not record or record.device_id != device_id: raise HTTPException(404, "Configuration version not found")
    if record.retention_state != "active": raise HTTPException(410, "Configuration artifact expired")
    return {"version_id": record.id, "sha256": record.sha256, "content": backup_service.configurations.content(record)}


@app.get("/api/devices/{device_id}/configurations/{version_a}/diff/{version_b}")
def diff_configurations(device_id: str, version_a: str, version_b: str, session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    left, right = session.get(ConfigurationVersionRecord, version_a), session.get(ConfigurationVersionRecord, version_b)
    if not left or not right or left.device_id != device_id or right.device_id != device_id:
        raise HTTPException(404, "Configuration version not found")
    return configuration_diff(backup_service.configurations.content(left), backup_service.configurations.content(right))


# --- Phase 3: topology -------------------------------------------------------------
# Read-only views over the same inventory rows the pages above use. No separate
# topology store, and every payload is built from discovered evidence only.

@app.get("/api/topology")
def get_topology(filters: dict = Depends(topology_filters)):
    return topology_service.graph(**filters)


@app.get("/api/topology/nodes")
def get_topology_nodes(filters: dict = Depends(topology_filters)):
    return topology_service.nodes(**filters)


@app.get("/api/topology/edges")
def get_topology_edges(filters: dict = Depends(topology_filters)):
    return topology_service.edges(**filters)


@app.get("/api/topology/devices/{device_id}")
def get_device_topology(device_id: str):
    """Ego graph for the details drawer: the device, its links, and the far endpoints."""
    try:
        return topology_service.device_slice(device_id)
    except KeyError as exc:
        raise HTTPException(404, "Device not found in topology") from exc


# Declared last so the static paths above are never mistaken for a site name.
@app.get("/api/topology/{site}")
def get_site_topology(site: str):
    return topology_service.graph(site=site)


# --- Phase 3: device lifecycle ----------------------------------------------------
# Administrative writes. The row holds a credential *reference*; DeviceInput forbids
# unknown fields, so a posted password is a 422 rather than a silent secret in the DB.

@app.get("/api/devices/{device_id}/summary")
def get_device_summary(device_id: str, session: Session = Depends(get_session)):
    """Drawer payload: inventory row plus counts. Never reads configuration artifacts."""
    record = session.get(DeviceRecord, device_id)
    if not record:
        raise HTTPException(404, "Device not found")

    def last_success(action: str):
        return session.scalar(select(func.max(AuditLogRecord.created_at)).where(
            AuditLogRecord.action == action, AuditLogRecord.resource_id == device_id,
            AuditLogRecord.result == "SUCCESS"))

    return {**InventoryService.serialize(record), **inventory_service.counts(device_id),
            "last_backup_at": last_success("BACKUP_CONFIGURATION"),
            "last_discovery_at": last_success("DEVICE_DISCOVERY")}


@app.post("/api/devices", status_code=201)
def create_device(payload: DeviceInput, actor: str = Depends(require_admin)):
    try:
        return inventory_service.create(payload, actor=actor)
    except DeviceConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@app.put("/api/devices/{device_id}")
def update_device(device_id: str, payload: DeviceInput, actor: str = Depends(require_admin)):
    try:
        return inventory_service.update(device_id, payload, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Device not found") from exc
    except DeviceConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str, actor: str = Depends(require_admin)):
    try:
        return inventory_service.delete(device_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Device not found") from exc


@app.post("/api/devices/{device_id}/discovery")
def discover_device(device_id: str, session: Session = Depends(get_session), _actor: str = Depends(require_backup_operator)):
    """Run the existing Phase 1 discovery against one stored device. No second implementation."""
    record = session.get(DeviceRecord, device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    target = DiscoveryTarget(
        name=record.name, management_ip=record.management_ip, type=record.type,
        credentials_reference_id=record.credentials_reference_id, vendor=record.vendor,
        site=record.site, port=record.management_port or 22)
    return service.run([target])


# --- Phase 3: schedules -----------------------------------------------------------
# Every run goes through ScheduleService -> BackupService; there is no second
# backup path and no legacy scheduler.

@app.get("/api/schedules")
def list_schedules():
    return schedule_service.list()


@app.post("/api/schedules", status_code=201)
def create_schedule(spec: ScheduleSpec, actor: str = Depends(require_admin)):
    try:
        return schedule_service.create(spec, actor=actor)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/schedules/{schedule_id}")
def get_schedule(schedule_id: str):
    try:
        return schedule_service.get(schedule_id)
    except KeyError as exc:
        raise HTTPException(404, "Schedule not found") from exc


@app.put("/api/schedules/{schedule_id}")
def update_schedule(schedule_id: str, spec: ScheduleSpec, actor: str = Depends(require_admin)):
    try:
        return schedule_service.update(schedule_id, spec, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Schedule not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/schedules/{schedule_id}/enabled")
def set_schedule_enabled(schedule_id: str, enabled: bool = Query(...), actor: str = Depends(require_admin)):
    try:
        return schedule_service.set_enabled(schedule_id, enabled, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Schedule not found") from exc


@app.delete("/api/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, actor: str = Depends(require_admin)):
    try:
        schedule_service.delete(schedule_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Schedule not found") from exc
    return Response(status_code=204)


@app.post("/api/schedules/{schedule_id}/run", status_code=202)
def run_schedule(schedule_id: str, background: BackgroundTasks, _actor: str = Depends(require_backup_operator)):
    """Run a schedule off-cycle. Same BackupService, same job table as POST /api/backups."""
    try:
        schedule_service.get(schedule_id)
    except KeyError as exc:
        raise HTTPException(404, "Schedule not found") from exc
    background.add_task(schedule_service.run, schedule_id)
    return {"schedule_id": schedule_id, "status": "STARTED"}


@app.get("/api/scheduler")
def scheduler_status():
    return {"running": schedule_runner.is_started(), "tick_seconds": schedule_runner.tick_seconds,
            "due_now": len(schedule_service.due())}


# --- Phase 3: logs and dashboard --------------------------------------------------

@app.get("/api/logs")
def list_logs(session: Session = Depends(get_session), start: datetime | None = None,
              end: datetime | None = None, device_id: str | None = None, category: str | None = None,
              status: str | None = None, search: str | None = None,
              limit: int = Query(default=200, ge=1, le=1000)):
    """Structured audit/job feed. Secret-shaped keys and raw command output are stripped."""
    return query_events(session, start=start, end=end, device_id=device_id, category=category,
                        status=status, search=search, limit=limit)


@app.get("/api/logs/options")
def log_options(session: Session = Depends(get_session)):
    devices = session.execute(select(DeviceRecord.id, DeviceRecord.name).order_by(DeviceRecord.name)).all()
    return {"categories": list(CATEGORIES), "statuses": list(STATUSES),
            "devices": [{"id": device_id, "name": name} for device_id, name in devices]}


@app.get("/api/dashboard")
def dashboard(session: Session = Depends(get_session)):
    return build_summary(session, topology_service.graph()["stats"])
