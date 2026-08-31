"""
Phase 4 — Alerts Service.

Generates alerts from findings and direct monitoring events.
Deduplication: identical (device_id, category, title) with status="new"
is not duplicated — the existing alert's created_at is left unchanged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, select

from database.models import AlertRecord

log = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset({
    "policy_violation",
    "config_change",
    "service_exposure",
    "device_unreachable",
    "high_cpu",
    "high_temperature",
    "interface_error",
    "power_issue",
    "fan_issue",
    "discovery_failure",
    "other",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertsService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def emit_alert(
        self,
        category: str,
        severity: str,
        title: str,
        device_id: str | None = None,
        finding_id: str | None = None,
        message: str | None = None,
        actor: str = "system",
        evidence_ref: str | None = None,
    ) -> dict:
        """
        Create or re-use an existing open alert with identical identity.
        Returns serialized alert dict.
        """
        if category not in VALID_CATEGORIES:
            category = "other"
        now = _utcnow()

        with self._session_factory() as session:
            # Deduplication: same (device, category, title) while still "new"
            existing = session.scalar(
                select(AlertRecord).where(
                    and_(
                        AlertRecord.device_id == device_id,
                        AlertRecord.category == category,
                        AlertRecord.title == title,
                        AlertRecord.status == "new",
                    )
                ).limit(1)
            )
            if existing:
                return self._serialize(existing)

            alert = AlertRecord(
                id=str(uuid4()),
                finding_id=finding_id,
                device_id=device_id,
                category=category,
                severity=severity,
                status="new",
                title=title,
                message=message,
                created_at=now,
                actor=actor,
                evidence_ref=evidence_ref,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            return self._serialize(alert)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def acknowledge(self, alert_id: str, actor: str) -> dict:
        now = _utcnow()
        with self._session_factory() as session:
            alert = session.get(AlertRecord, alert_id)
            if not alert:
                raise KeyError(alert_id)
            alert.status = "acknowledged"
            alert.acknowledged_at = now
            alert.actor = actor
            session.commit()
            session.refresh(alert)
            return self._serialize(alert)

    def resolve(self, alert_id: str, actor: str) -> dict:
        now = _utcnow()
        with self._session_factory() as session:
            alert = session.get(AlertRecord, alert_id)
            if not alert:
                raise KeyError(alert_id)
            alert.status = "resolved"
            alert.resolved_at = now
            alert.actor = actor
            session.commit()
            session.refresh(alert)
            return self._serialize(alert)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list(
        self,
        severity: str | None = None,
        status: str | None = None,
        device_id: str | None = None,
        category: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        with self._session_factory() as session:
            q = select(AlertRecord)
            if severity:
                q = q.where(AlertRecord.severity == severity)
            if status:
                q = q.where(AlertRecord.status == status)
            if device_id:
                q = q.where(AlertRecord.device_id == device_id)
            if category:
                q = q.where(AlertRecord.category == category)
            q = q.order_by(AlertRecord.created_at.desc()).limit(limit)
            return [self._serialize(a) for a in session.scalars(q)]

    def get(self, alert_id: str) -> dict:
        with self._session_factory() as session:
            alert = session.get(AlertRecord, alert_id)
            if not alert:
                raise KeyError(alert_id)
            return self._serialize(alert)

    def summary_counts(self) -> dict:
        from sqlalchemy import func
        with self._session_factory() as session:
            rows = session.execute(
                select(AlertRecord.severity, AlertRecord.status, func.count())
                .group_by(AlertRecord.severity, AlertRecord.status)
            ).all()
        counts: dict = {
            "new": 0, "acknowledged": 0, "resolved": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "by_category": {},
        }
        for severity, status, count in rows:
            if status in counts:
                counts[status] += count
            if severity in counts["by_severity"]:
                counts["by_severity"][severity] += count
        counts["total"] = counts["new"] + counts["acknowledged"]
        return counts

    @staticmethod
    def _serialize(alert: AlertRecord) -> dict:
        return {
            "id": alert.id,
            "finding_id": alert.finding_id,
            "device_id": alert.device_id,
            "category": alert.category,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "message": alert.message,
            "created_at": alert.created_at,
            "acknowledged_at": alert.acknowledged_at,
            "resolved_at": alert.resolved_at,
            "actor": alert.actor,
            "evidence_ref": alert.evidence_ref,
        }
