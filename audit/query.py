"""Read-only queries over the structured audit trail.

The Logs screen is a view of records the platform already writes — audit rows and
backup jobs — not a second logging system.  Two rules apply on the way out:
secrets are never selected in the first place (writers strip them), and raw device
command output is not part of an audit row, so it cannot leak here either.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AuditLogRecord, BackupJobRecord, DeviceRecord

#: Filter options offered to the UI. "authentication" is derived, not an action name.
CATEGORIES = ("discovery", "backup", "schedule", "device", "authentication", "system")
STATUSES = ("SUCCESS", "PARTIAL", "FAILED", "PENDING", "RUNNING")

_ACTION_CATEGORY = {
    "DEVICE_DISCOVERY": "discovery",
    "BACKUP_CONFIGURATION": "backup",
    "DEVICE_CREATED": "device",
    "DEVICE_UPDATED": "device",
    "DEVICE_DELETED": "device",
}
_SECRETISH = ("password", "secret", "credential", "private_key", "passphrase", "token", "community")
_AUTH_MARKERS = ("authentication", "auth_failed", "credential")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def safe_details(details: object) -> dict:
    """Drop anything secret-shaped and any bulk command/configuration payload."""
    if not isinstance(details, dict):
        return {}
    return {key: value for key, value in details.items()
            if not any(marker in key.lower() for marker in _SECRETISH)
            and key not in {"raw", "configuration", "output", "content"}}


def _category(record: AuditLogRecord) -> str:
    if record.action.startswith("SCHEDULE_"):
        return "schedule"
    details = record.details if isinstance(record.details, dict) else {}
    error = str(details.get("error_category", "")).casefold()
    if record.result == "FAILED" and any(marker in error for marker in _AUTH_MARKERS):
        return "authentication"
    return _ACTION_CATEGORY.get(record.action, "system")


def _summary(record: AuditLogRecord, category: str, device_name: str | None) -> str:
    details = record.details if isinstance(record.details, dict) else {}
    subject = device_name or details.get("schedule") or details.get("target") or record.resource_id
    if category == "authentication":
        return f"Authentication failed for {subject}"
    if error := details.get("error_category"):
        return f"{record.action.replace('_', ' ').capitalize()} failed for {subject}: {error}"
    if change := details.get("change_status"):
        return f"{record.action.replace('_', ' ').capitalize()} on {subject}: {change.replace('_', ' ').lower()}"
    return f"{record.action.replace('_', ' ').capitalize()} on {subject}"


def query_events(
    session: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    device_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Merged, newest-first event feed. Filtering happens in SQL where it can."""
    limit = max(1, min(int(limit), 1000))
    names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())

    audit = select(AuditLogRecord)
    if start:
        audit = audit.where(AuditLogRecord.created_at >= start)
    if end:
        audit = audit.where(AuditLogRecord.created_at <= end)
    if device_id:
        audit = audit.where(AuditLogRecord.resource_id == device_id)
    if status:
        audit = audit.where(AuditLogRecord.result == status.upper())
    rows = list(session.scalars(audit.order_by(AuditLogRecord.created_at.desc()).limit(limit * 2)))

    events = []
    for record in rows:
        event_category = _category(record)
        device_name = names.get(record.resource_id)
        events.append({
            "id": record.id, "timestamp": _aware(record.created_at), "category": event_category,
            "event": record.action, "actor": record.actor, "status": record.result,
            "device_id": record.resource_id if device_name else None, "device": device_name,
            "resource_type": record.resource_type, "resource_id": record.resource_id,
            "correlation_id": record.correlation_id,
            "summary": _summary(record, event_category, device_name),
            "details": safe_details(record.details),
        })

    if not device_id:  # job rows summarize many devices, so they have no single device scope
        jobs = select(BackupJobRecord)
        if start:
            jobs = jobs.where(BackupJobRecord.created_at >= start)
        if end:
            jobs = jobs.where(BackupJobRecord.created_at <= end)
        if status:
            jobs = jobs.where(BackupJobRecord.status == status.upper())
        for job in session.scalars(jobs.order_by(BackupJobRecord.created_at.desc()).limit(limit)):
            events.append({
                "id": f"job:{job.id}", "timestamp": _aware(job.completed_at or job.created_at),
                "category": "backup", "event": "BACKUP_JOB", "actor": job.requested_by,
                "status": job.status, "device_id": None, "device": None,
                "resource_type": "backup_job", "resource_id": job.id, "correlation_id": job.id,
                "summary": (f"Backup job {job.status.lower()}: {job.success_count} succeeded, "
                            f"{job.failure_count} failed across {len(job.target_scope)} device(s)"),
                "details": {"success_count": job.success_count, "failure_count": job.failure_count,
                            "device_count": len(job.target_scope)},
            })

    if category and category.casefold() != "all":
        events = [event for event in events if event["category"] == category.casefold()]
    if search:
        needle = search.casefold()
        events = [event for event in events
                  if needle in event["summary"].casefold() or needle in event["actor"].casefold()
                  or needle in event["event"].casefold()]
    events.sort(key=lambda event: (event["timestamp"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return events[:limit]
