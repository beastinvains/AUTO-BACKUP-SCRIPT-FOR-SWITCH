"""Dashboard read model.

Aggregates that already exist elsewhere, counted in SQL rather than by loading rows:
infrastructure, topology, backup, and discovery. No derived scores, no predictions —
Phase 3 shows what the database can prove.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from database.models import AuditLogRecord, BackupJobRecord, DeviceRecord, ScheduleRecord

STALE_BACKUP_DAYS = 7


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_summary(session, topology_stats: dict) -> dict:
    """One dashboard payload; ``topology_stats`` comes from the graph service."""
    now = datetime.now(timezone.utc)
    by_status = dict(session.execute(
        select(DeviceRecord.status, func.count(DeviceRecord.id)).group_by(DeviceRecord.status)).all())
    by_vendor = dict(session.execute(
        select(DeviceRecord.vendor, func.count(DeviceRecord.id)).group_by(DeviceRecord.vendor)).all())
    total_devices = sum(by_status.values())

    last_success = session.scalar(
        select(func.max(BackupJobRecord.completed_at)).where(BackupJobRecord.status == "SUCCESS"))
    failed_jobs = session.scalar(
        select(func.count(BackupJobRecord.id)).where(BackupJobRecord.status.in_(("FAILED", "PARTIAL")))) or 0
    backed_up = dict(session.execute(
        select(AuditLogRecord.resource_id, func.max(AuditLogRecord.created_at))
        .where(AuditLogRecord.action == "BACKUP_CONFIGURATION", AuditLogRecord.result == "SUCCESS")
        .group_by(AuditLogRecord.resource_id)).all())
    cutoff = now - timedelta(days=STALE_BACKUP_DAYS)
    device_ids = list(session.scalars(select(DeviceRecord.id)))
    stale = [device_id for device_id in device_ids
             if (last := _aware(backed_up.get(device_id))) is None or last < cutoff]

    last_discovery = session.scalar(
        select(func.max(AuditLogRecord.created_at)).where(AuditLogRecord.action == "DEVICE_DISCOVERY"))
    failed_discovery = session.scalar(
        select(func.count(AuditLogRecord.id))
        .where(AuditLogRecord.action == "DEVICE_DISCOVERY", AuditLogRecord.result == "FAILED")) or 0

    return {
        "generated_at": now,
        "infrastructure": {
            "total_devices": total_devices,
            "online": by_status.get("online", 0),
            "offline": by_status.get("offline", 0),
            "degraded": by_status.get("degraded", 0),
            "unknown": by_status.get("unknown", 0),
            # only vendors actually present are reported; nothing is invented for absent ones
            "by_vendor": {vendor or "unidentified": count for vendor, count in sorted(
                by_vendor.items(), key=lambda item: (item[0] or ""))},
        },
        "topology": {
            "nodes": topology_stats.get("node_count", 0),
            "devices": topology_stats.get("device_count", 0),
            "connections": topology_stats.get("edge_count", 0),
            "corroborated_connections": topology_stats.get("corroborated_edges", 0),
            "unresolved_neighbors": topology_stats.get("unresolved_neighbors", 0),
            "external_nodes": topology_stats.get("external_count", 0),
            "ambiguous_identities": len(topology_stats.get("ambiguous_identities", [])),
        },
        "backup": {
            "last_successful_backup": _aware(last_success),
            "failed_jobs": failed_jobs,
            "devices_never_backed_up": sum(device_id not in backed_up for device_id in device_ids),
            "devices_stale_backup": len(stale),
            "stale_threshold_days": STALE_BACKUP_DAYS,
            "total_jobs": session.scalar(select(func.count(BackupJobRecord.id))) or 0,
        },
        "discovery": {
            "last_discovery": _aware(last_discovery),
            "failed_discoveries": failed_discovery,
            "pending_devices": session.scalar(select(func.count(DeviceRecord.id))
                                              .where(DeviceRecord.discovery_state == "pending")) or 0,
        },
        "schedules": {
            "total": session.scalar(select(func.count(ScheduleRecord.id))) or 0,
            "enabled": session.scalar(select(func.count(ScheduleRecord.id))
                                      .where(ScheduleRecord.enabled.is_(True))) or 0,
            "next_run_at": _aware(session.scalar(select(func.min(ScheduleRecord.next_run_at))
                                                .where(ScheduleRecord.enabled.is_(True)))),
        },
    }
