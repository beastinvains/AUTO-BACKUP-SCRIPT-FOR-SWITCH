"""
Phase 4 — Security Reports Service.

Generates reproducible security assessment reports entirely from stored data.
No live device calls.  Report content is built from:
  - Latest TelemetryRecord per device
  - Open/acknowledged FindingRecord rows
  - AlertRecord summary
  - PolicyEvaluationRecord pass/fail counts

Reports can be stored as EvidenceRecords for audit purposes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from database.models import (
    AlertRecord,
    DeviceRecord,
    FindingRecord,
    MonitoringJobRecord,
    PolicyEvaluationRecord,
    PolicyRecord,
    SecurityReportRecord,
    TelemetryRecord,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReportsService:
    def __init__(self, session_factory, evidence_service=None):
        self._session_factory = session_factory
        self._evidence = evidence_service

    # ------------------------------------------------------------------
    # Security Posture (lightweight, for dashboard)
    # ------------------------------------------------------------------

    def get_security_posture(self) -> dict:
        """Estate-wide security posture — aggregated from stored data."""
        with self._session_factory() as session:
            total_devices = session.scalar(select(func.count(DeviceRecord.id))) or 0
            # Findings
            finding_rows = session.execute(
                select(FindingRecord.severity, FindingRecord.status, func.count())
                .group_by(FindingRecord.severity, FindingRecord.status)
            ).all()
            # Alerts
            alert_rows = session.execute(
                select(AlertRecord.severity, AlertRecord.status, func.count())
                .group_by(AlertRecord.severity, AlertRecord.status)
            ).all()
            # Policy evaluations (most recent per policy per device)
            total_evals = session.scalar(select(func.count(PolicyEvaluationRecord.id))) or 0
            pass_evals = session.scalar(
                select(func.count(PolicyEvaluationRecord.id))
                .where(PolicyEvaluationRecord.result == "pass")
            ) or 0
            fail_evals = session.scalar(
                select(func.count(PolicyEvaluationRecord.id))
                .where(PolicyEvaluationRecord.result == "fail")
            ) or 0
            # Online devices (from latest telemetry)
            latest_online = session.scalar(
                select(func.count(TelemetryRecord.id)).where(
                    TelemetryRecord.reachability == "online"
                )
            ) or 0

        findings: dict = {
            "open": 0, "acknowledged": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        }
        for sev, status, cnt in finding_rows:
            if status in ("open", "acknowledged"):
                findings[status] = findings.get(status, 0) + cnt
            if sev in findings["by_severity"]:
                if status in ("open", "acknowledged"):
                    findings["by_severity"][sev] += cnt

        alerts: dict = {
            "new": 0, "acknowledged": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        }
        for sev, status, cnt in alert_rows:
            if status in ("new", "acknowledged"):
                alerts[status] = alerts.get(status, 0) + cnt
            if sev in alerts["by_severity"]:
                if status in ("new", "acknowledged"):
                    alerts["by_severity"][sev] += cnt

        compliance_score = None
        if total_evals > 0:
            compliance_score = round(pass_evals / total_evals * 100, 1)

        return {
            "generated_at": _utcnow(),
            "total_devices": total_devices,
            "findings": findings,
            "alerts": alerts,
            "compliance": {
                "score": compliance_score,
                "total_evaluations": total_evals,
                "pass": pass_evals,
                "fail": fail_evals,
                "unknown": total_evals - pass_evals - fail_evals,
            },
        }

    # ------------------------------------------------------------------
    # Full device report
    # ------------------------------------------------------------------

    def generate_device_report(self, device_id: str, actor: str) -> dict:
        """Generate and optionally store a full device security report."""
        now = _utcnow()
        with self._session_factory() as session:
            device = session.get(DeviceRecord, device_id)
            if not device:
                raise KeyError(device_id)

            # Telemetry summary
            latest_tel = session.scalar(
                select(TelemetryRecord)
                .where(TelemetryRecord.device_id == device_id)
                .order_by(TelemetryRecord.collected_at.desc())
                .limit(1)
            )
            telemetry_summary = {}
            if latest_tel:
                telemetry_summary = {
                    "collected_at": latest_tel.collected_at,
                    "reachability": latest_tel.reachability,
                    "cpu_percent": latest_tel.cpu_percent,
                    "memory_percent": latest_tel.memory_percent,
                    "temperature_c": latest_tel.temperature_c,
                    "fan_speed_rpm": latest_tel.fan_speed_rpm,
                    "power_status": latest_tel.power_status,
                    "interface_summary": latest_tel.interface_summary,
                }

            # Findings summary
            finding_rows = session.execute(
                select(FindingRecord.severity, FindingRecord.status, func.count())
                .where(FindingRecord.device_id == device_id)
                .group_by(FindingRecord.severity, FindingRecord.status)
            ).all()
            findings_summary = _count_by_sev_status(finding_rows)

            # Compliance evaluation summary
            eval_rows = session.execute(
                select(PolicyEvaluationRecord.result, func.count())
                .where(PolicyEvaluationRecord.device_id == device_id)
                .group_by(PolicyEvaluationRecord.result)
            ).all()
            compliance_summary = {r: c for r, c in eval_rows}
            total = sum(compliance_summary.values())
            score = round(compliance_summary.get("pass", 0) / total * 100, 1) if total else None

        report = {
            "device_id": device_id,
            "device_name": device.name,
            "generated_at": now,
            "generated_by": actor,
            "telemetry_summary": telemetry_summary,
            "findings_summary": findings_summary,
            "compliance_summary": {**compliance_summary, "score": score, "total": total},
            "service_summary": {},
        }

        # Optionally store as an evidence record
        evidence_refs = []
        if self._evidence:
            try:
                ev = self._evidence.store(
                    data=report,
                    evidence_type="report",
                    device_id=device_id,
                    source_adapter="reports_service",
                    metadata={"generated_by": actor},
                )
                evidence_refs.append(ev.id)
            except Exception:
                log.exception("failed to store device report evidence for %s", device_id)

        # Persist SecurityReportRecord
        with self._session_factory() as session:
            rec = SecurityReportRecord(
                device_id=device_id,
                generated_at=now,
                generated_by=actor,
                evidence_refs=evidence_refs,
                compliance_summary=report["compliance_summary"],
                findings_summary=report["findings_summary"],
                telemetry_summary=report["telemetry_summary"],
                service_summary={},
            )
            session.add(rec)
            session.commit()
            session.refresh(rec)
            report["report_id"] = rec.id

        return report

    def generate_estate_report(self, actor: str) -> dict:
        """Estate-wide report."""
        now = _utcnow()
        posture = self.get_security_posture()

        with self._session_factory() as session:
            devices = list(session.scalars(select(DeviceRecord)))

        report = {
            "scope": "estate",
            "generated_at": now,
            "generated_by": actor,
            "total_devices": len(devices),
            "security_posture": posture,
        }

        with self._session_factory() as session:
            rec = SecurityReportRecord(
                device_id=None,
                generated_at=now,
                generated_by=actor,
                evidence_refs=[],
                compliance_summary=posture.get("compliance", {}),
                findings_summary=posture.get("findings", {}),
                telemetry_summary={},
                service_summary={},
            )
            session.add(rec)
            session.commit()
            session.refresh(rec)
            report["report_id"] = rec.id

        return report

    def get_report(self, report_id: str) -> dict | None:
        with self._session_factory() as session:
            rec = session.get(SecurityReportRecord, report_id)
            if not rec:
                return None
            return {
                "id": rec.id,
                "device_id": rec.device_id,
                "generated_at": rec.generated_at,
                "generated_by": rec.generated_by,
                "evidence_refs": rec.evidence_refs,
                "compliance_summary": rec.compliance_summary,
                "findings_summary": rec.findings_summary,
                "telemetry_summary": rec.telemetry_summary,
                "service_summary": rec.service_summary,
            }


def _count_by_sev_status(rows) -> dict:
    out: dict = {
        "open": 0, "acknowledged": 0, "resolved": 0,
        "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
    }
    for sev, status, cnt in rows:
        out[status] = out.get(status, 0) + cnt
        if sev in out["by_severity"]:
            out["by_severity"][sev] += cnt
    return out
