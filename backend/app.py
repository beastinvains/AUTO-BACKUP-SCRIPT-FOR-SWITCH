from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from adapters.juniper.adapter import JuniperAdapter
from alerts.service import AlertsService
from audit.query import CATEGORIES, STATUSES, query_events
from backend.dashboard import build_summary
from config import SETTINGS_FILE, load_config, load_settings
from configuration.service import ConfigurationService, configuration_diff
from core.models import DiscoveryTarget
from database.models import Base
from database.models import AuditLogRecord, BackupJobRecord, ConfigurationVersionRecord, DeviceRecord
from database.session import SessionLocal, engine
from discovery.jobs import DiscoveryService
from evidence.service import EvidenceService
from findings.service import FindingsService
from inventory.repository import InventoryRepository
from inventory.service import DeviceConflict, DeviceInput, InventoryService
from backup_service import BackupService
from monitoring.service import MonitoringService
from policy.service import PolicyInput, PolicyService
from policy.seed_policies import seed as seed_default_policies
from reports.service import ReportsService
from schedule_service import ScheduleService, ScheduleSpec
from scheduler import ScheduleRunner
from storage.local import LocalArtifactStorage
from topology.service import TopologyService


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Seed the 7 default security policies on first startup (idempotent).
    seed_default_policies(SessionLocal)
    # Nothing runs until an operator creates a schedule, so starting the clock here is
    # inert on a fresh database and keeps one scheduler in one place.
    schedule_runner.start()
    try:
        yield
    finally:
        schedule_runner.stop()


app = FastAPI(title="Infrastructure Vision Platform - Phase 4", lifespan=lifespan)
# The React (Vite) client runs on http://localhost:5173 in development. The dev
# server also proxies /api, so this is a belt-and-suspenders allowance and lets a
# production build call the API directly. X-Role/X-Actor are covered by "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Shared singletons --------------------------------------------------
_config = load_config()
_adapter = JuniperAdapter()
_cfg_service = ConfigurationService(LocalArtifactStorage(_config.backup_root))
_evidence_service = EvidenceService(SessionLocal, _config.backup_root)
_alerts_service = AlertsService(SessionLocal)
_findings_service = FindingsService(SessionLocal, alerts_service=_alerts_service)
_policy_service = PolicyService(SessionLocal, findings_service=_findings_service)
_monitoring_service = MonitoringService(
    SessionLocal, _adapter, _cfg_service,
    evidence_service=_evidence_service,
    alerts_service=_alerts_service,
)
_reports_service = ReportsService(SessionLocal, evidence_service=_evidence_service)

service = DiscoveryService(_adapter, SessionLocal)
backup_service = BackupService(_adapter, SessionLocal, _cfg_service)
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


class SettingsInput(BaseModel):
    backup_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d")
    backup_directory: str = Field(min_length=1, max_length=1024)
    max_workers: int = Field(ge=1, le=64)
    retention_days: int = Field(ge=1, le=3650)


def topology_filters(site: str | None = None, vendor: str | None = None,
                     device_type: str | None = None, status: str | None = None,
                     show_end_devices: bool = False) -> dict:
    """Query filters shared by every topology route (Phase 3 section 12)."""
    return {"site": site, "vendor": vendor, "device_type": device_type, "status": status, "show_end_devices": show_end_devices}


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


@app.get("/api/settings")
def get_settings():
    config = load_config()
    stored = load_settings()
    return {"backup_time": stored.get("backup_time", config.backup_time),
            "backup_directory": stored.get("backup_directory", str(config.backup_root)),
            "max_workers": stored.get("max_workers", config.max_workers),
            "retention_days": stored.get("retention_days", config.retention_days)}


@app.put("/api/settings")
def update_settings(payload: SettingsInput, _actor: str = Depends(require_admin)):
    settings = load_settings()
    settings.update(payload.model_dump())
    temporary = SETTINGS_FILE.with_suffix(".json.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        import json
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    temporary.replace(SETTINGS_FILE)
    # BackupService is created at module import time; refresh its artifact store so a
    # directory changed in Settings is used by the next backup in this process.
    backup_service.configurations.storage = LocalArtifactStorage(load_config().backup_root)
    return get_settings()


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
    base = build_summary(session, topology_service.graph()["stats"])
    try:
        base["security_posture"] = _reports_service.get_security_posture()
    except Exception:
        base["security_posture"] = None
    return base


@app.get("/api/compliance/trend")
def compliance_trend(
    days: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
):
    """Historical compliance scores over time for trend chart."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from database.models import PolicyEvaluationRecord

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    # Get evaluations grouped by day
    evals = session.execute(
        select(
            func.date(PolicyEvaluationRecord.evaluated_at).label("eval_date"),
            func.count().label("total"),
            func.sum(func.cast(PolicyEvaluationRecord.result == "pass", Integer)).label("pass_count"),
        )
        .where(PolicyEvaluationRecord.evaluated_at >= start)
        .group_by(func.date(PolicyEvaluationRecord.evaluated_at))
        .order_by(func.date(PolicyEvaluationRecord.evaluated_at))
    ).all()

    points = []
    for row in evals:
        date_str = str(row.eval_date)
        total = row.total or 0
        pass_count = row.pass_count or 0
        score = round((pass_count / total) * 100, 1) if total > 0 else 0
        points.append({"date": date_str, "value": score})

    return {"days": days, "points": points}


# ---------------------------------------------------------------------------
# Phase 4: Monitoring
# ---------------------------------------------------------------------------

@app.get("/api/monitoring")
def monitoring_overview():
    """Estate-wide monitoring coverage: last collection per device, reachability, telemetry values."""
    return _monitoring_service.get_monitoring_overview()


@app.get("/api/monitoring/devices/{device_id}")
def monitoring_device(device_id: str, session: Session = Depends(get_session)):
    """Latest telemetry + service observations for one device."""
    if not session.get(DeviceRecord, device_id):
        raise HTTPException(404, "Device not found")
    telemetry = _monitoring_service.get_latest_telemetry(device_id)
    services = _monitoring_service.get_service_observations(device_id)
    return {"telemetry": telemetry, "services": services}


@app.get("/api/monitoring/history/{device_id}")
def monitoring_history(
    device_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    if not session.get(DeviceRecord, device_id):
        raise HTTPException(404, "Device not found")
    return _monitoring_service.get_telemetry_history(device_id, start=start, end=end, limit=limit)


@app.post("/api/monitoring/run", status_code=202)
def run_monitoring(
    background: BackgroundTasks,
    kind: str = Query(default="telemetry", pattern=r"^(telemetry|service|all)$"),
    device_ids: list[str] = Query(default=[]),
    actor: str = Depends(require_backup_operator),
):
    """Trigger a manual monitoring collection run in the background."""
    actual_ids = device_ids or None
    background.add_task(
        _monitoring_service.run_collection,
        kind=kind,
        device_ids=actual_ids,
        triggered_by="manual",
    )
    return {"status": "STARTED", "kind": kind}


# ---------------------------------------------------------------------------
# Phase 4: Policies
# ---------------------------------------------------------------------------

@app.get("/api/policies")
def list_policies(
    category: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
):
    return _policy_service.list(category=category, severity=severity, enabled=enabled)


@app.post("/api/policies", status_code=201)
def create_policy(payload: PolicyInput, actor: str = Depends(require_admin)):
    try:
        return _policy_service.create(payload, actor=actor)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/policies/{policy_id}")
def get_policy(policy_id: str):
    try:
        return _policy_service.get(policy_id)
    except KeyError as exc:
        raise HTTPException(404, "Policy not found") from exc


@app.put("/api/policies/{policy_id}")
def update_policy(policy_id: str, payload: PolicyInput, actor: str = Depends(require_admin)):
    try:
        return _policy_service.update(policy_id, payload, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Policy not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.delete("/api/policies/{policy_id}", status_code=204)
def delete_policy(policy_id: str, actor: str = Depends(require_admin)):
    try:
        _policy_service.delete(policy_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Policy not found") from exc
    return Response(status_code=204)


@app.post("/api/policies/{policy_id}/evaluate", status_code=202)
def evaluate_policy(
    policy_id: str,
    device_ids: list[str] = Query(default=[]),
    background: BackgroundTasks = BackgroundTasks(),
    actor: str = Depends(require_backup_operator),
):
    """Evaluate a policy across all applicable devices (async)."""
    try:
        _policy_service.get(policy_id)  # 404 check
    except KeyError as exc:
        raise HTTPException(404, "Policy not found") from exc
    actual_ids = device_ids or None
    background.add_task(_policy_service.evaluate_policy, policy_id, actual_ids)
    return {"policy_id": policy_id, "status": "EVALUATING"}


# ---------------------------------------------------------------------------
# Phase 4: Findings
# ---------------------------------------------------------------------------

@app.get("/api/findings")
def list_findings(
    severity: str | None = None,
    status: str | None = None,
    device_id: str | None = None,
    policy_id: str | None = None,
    category: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    return _findings_service.list(
        severity=severity, status=status, device_id=device_id,
        policy_id=policy_id, category=category, start=start, end=end, limit=limit,
    )


@app.get("/api/findings/{finding_id}")
def get_finding(finding_id: str):
    try:
        return _findings_service.get(finding_id)
    except KeyError as exc:
        raise HTTPException(404, "Finding not found") from exc


@app.post("/api/findings/{finding_id}/acknowledge")
def acknowledge_finding(finding_id: str, actor: str = Depends(require_backup_operator)):
    try:
        return _findings_service.acknowledge(finding_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Finding not found") from exc


@app.post("/api/findings/{finding_id}/resolve")
def resolve_finding(
    finding_id: str,
    note: str | None = None,
    actor: str = Depends(require_backup_operator),
):
    try:
        return _findings_service.resolve(finding_id, actor=actor, note=note)
    except KeyError as exc:
        raise HTTPException(404, "Finding not found") from exc


@app.post("/api/findings/{finding_id}/suppress")
def suppress_finding(finding_id: str, actor: str = Depends(require_admin)):
    try:
        return _findings_service.suppress(finding_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Finding not found") from exc


# ---------------------------------------------------------------------------
# Phase 4: Alerts
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def list_alerts(
    severity: str | None = None,
    status: str | None = None,
    device_id: str | None = None,
    category: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    return _alerts_service.list(
        severity=severity, status=status, device_id=device_id,
        category=category, limit=limit,
    )


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: str):
    try:
        return _alerts_service.get(alert_id)
    except KeyError as exc:
        raise HTTPException(404, "Alert not found") from exc


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, actor: str = Depends(require_backup_operator)):
    try:
        return _alerts_service.acknowledge(alert_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Alert not found") from exc


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, actor: str = Depends(require_backup_operator)):
    try:
        return _alerts_service.resolve(alert_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Alert not found") from exc


# ---------------------------------------------------------------------------
# Phase 4: Evidence
# ---------------------------------------------------------------------------

@app.get("/api/evidence")
def list_evidence(device_id: str, evidence_type: str | None = None, limit: int = 100):
    return [
        _evidence_service.serialize(r)
        for r in _evidence_service.list_for_device(device_id, evidence_type, limit)
    ]


@app.get("/api/evidence/{evidence_id}")
def get_evidence(evidence_id: str):
    record = _evidence_service.get(evidence_id)
    if not record:
        raise HTTPException(404, "Evidence record not found")
    return _evidence_service.serialize(record)


# ---------------------------------------------------------------------------
# Phase 4: Security Posture and Reports
# ---------------------------------------------------------------------------

@app.get("/api/security-posture")
def security_posture():
    """Estate-wide real-time security posture derived from stored findings, alerts, telemetry."""
    return _reports_service.get_security_posture()


@app.post("/api/reports/device/{device_id}", status_code=201)
def generate_device_report(device_id: str, session: Session = Depends(get_session), actor: str = Depends(require_backup_operator)):
    if not session.get(DeviceRecord, device_id):
        raise HTTPException(404, "Device not found")
    try:
        return _reports_service.generate_device_report(device_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(404, "Device not found") from exc


@app.post("/api/reports/estate", status_code=201)
def generate_estate_report(actor: str = Depends(require_backup_operator)):
    return _reports_service.generate_estate_report(actor=actor)


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    report = _reports_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report

