"""
Phase 4 — Findings Service.

Deduplication rule: when an open Finding with the same
(device_id, policy_id, title) already exists, increment
occurrence_count and update last_seen_at — do NOT insert a new row.

Finding status lifecycle:
  open → acknowledged → resolved → (closed)
  open → suppressed
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from database.models import FindingRecord

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FindingsService:
    def __init__(self, session_factory, alerts_service=None):
        self._session_factory = session_factory
        self._alerts = alerts_service

    # ------------------------------------------------------------------
    # Write path (with deduplication)
    # ------------------------------------------------------------------

    def record_finding(
        self,
        device_id: str,
        severity: str,
        title: str,
        category: str,
        policy_id: str | None = None,
        description: str | None = None,
        evidence_refs: list[str] | None = None,
        related_config_version_id: str | None = None,
        related_telemetry_id: str | None = None,
    ) -> dict:
        """
        Create a new Finding or update an existing open one (deduplication).
        Returns serialized finding dict.
        """
        now = _utcnow()
        with self._session_factory() as session:
            # Look for an existing open/acknowledged finding for same device+policy+title
            existing = session.scalar(
                select(FindingRecord).where(
                    and_(
                        FindingRecord.device_id == device_id,
                        FindingRecord.policy_id == policy_id,
                        FindingRecord.title == title,
                        FindingRecord.status.in_(("open", "acknowledged")),
                    )
                ).limit(1)
            )

            if existing:
                existing.last_seen_at = now
                existing.occurrence_count += 1
                if evidence_refs:
                    existing.evidence_refs = (existing.evidence_refs or []) + evidence_refs
                session.commit()
                session.refresh(existing)
                return self._serialize(existing)

            # New finding
            finding = FindingRecord(
                id=str(uuid4()),
                device_id=device_id,
                policy_id=policy_id,
                severity=severity,
                status="open",
                title=title,
                description=description,
                category=category,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
                evidence_refs=evidence_refs or [],
                related_config_version_id=related_config_version_id,
                related_telemetry_id=related_telemetry_id,
                created_at=now,
            )
            session.add(finding)
            session.commit()
            session.refresh(finding)

        # Emit an alert for the new finding
        if self._alerts:
            try:
                self._alerts.emit_alert(
                    category="policy_violation",
                    device_id=device_id,
                    finding_id=finding.id,
                    severity=severity,
                    title=f"Finding: {title}",
                    message=description or "",
                    actor="policy_engine",
                )
            except Exception:
                log.exception("failed to emit alert for finding %s", finding.id)

        return self._serialize(finding)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def acknowledge(self, finding_id: str, actor: str) -> dict:
        return self._transition(finding_id, "acknowledged", actor)

    def resolve(self, finding_id: str, actor: str, note: str | None = None) -> dict:
        now = _utcnow()
        with self._session_factory() as session:
            finding = session.get(FindingRecord, finding_id)
            if not finding:
                raise KeyError(finding_id)
            finding.status = "resolved"
            finding.resolved_at = now
            finding.resolution_note = note
            session.commit()
            session.refresh(finding)
            return self._serialize(finding)

    def suppress(self, finding_id: str, actor: str) -> dict:
        return self._transition(finding_id, "suppressed", actor)

    def _transition(self, finding_id: str, new_status: str, actor: str) -> dict:
        with self._session_factory() as session:
            finding = session.get(FindingRecord, finding_id)
            if not finding:
                raise KeyError(finding_id)
            finding.status = new_status
            session.commit()
            session.refresh(finding)
            return self._serialize(finding)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list(
        self,
        severity: str | None = None,
        status: str | None = None,
        device_id: str | None = None,
        policy_id: str | None = None,
        category: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[dict]:
        with self._session_factory() as session:
            q = select(FindingRecord)
            if severity:
                q = q.where(FindingRecord.severity == severity)
            if status:
                q = q.where(FindingRecord.status == status)
            if device_id:
                q = q.where(FindingRecord.device_id == device_id)
            if policy_id:
                q = q.where(FindingRecord.policy_id == policy_id)
            if category:
                q = q.where(FindingRecord.category == category)
            if start:
                q = q.where(FindingRecord.first_seen_at >= start)
            if end:
                q = q.where(FindingRecord.first_seen_at <= end)
            q = q.order_by(FindingRecord.last_seen_at.desc()).limit(limit)
            return [self._serialize(f) for f in session.scalars(q)]

    def get(self, finding_id: str) -> dict:
        with self._session_factory() as session:
            finding = session.get(FindingRecord, finding_id)
            if not finding:
                raise KeyError(finding_id)
            return self._serialize(finding)

    def summary_counts(self) -> dict:
        """Returns counts by severity and status for dashboard/posture widgets."""
        from sqlalchemy import func
        with self._session_factory() as session:
            rows = session.execute(
                select(FindingRecord.severity, FindingRecord.status, func.count())
                .group_by(FindingRecord.severity, FindingRecord.status)
            ).all()
        counts: dict = {
            "open": 0, "acknowledged": 0, "resolved": 0, "suppressed": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        }
        for severity, status, count in rows:
            if status in counts:
                counts[status] += count
            if severity in counts["by_severity"]:
                counts["by_severity"][severity] += count
        counts["total"] = counts["open"] + counts["acknowledged"]
        return counts

    @staticmethod
    def _serialize(finding: FindingRecord) -> dict:
        return {
            "id": finding.id,
            "device_id": finding.device_id,
            "policy_id": finding.policy_id,
            "severity": finding.severity,
            "status": finding.status,
            "title": finding.title,
            "description": finding.description,
            "category": finding.category,
            "first_seen_at": finding.first_seen_at,
            "last_seen_at": finding.last_seen_at,
            "occurrence_count": finding.occurrence_count,
            "evidence_refs": finding.evidence_refs,
            "related_config_version_id": finding.related_config_version_id,
            "related_telemetry_id": finding.related_telemetry_id,
            "created_at": finding.created_at,
            "resolved_at": finding.resolved_at,
            "resolution_note": finding.resolution_note,
        }
