"""
Phase 4 — Policy Service.

CRUD + bulk evaluation for PolicyRecord.  Evaluation produces
PolicyEvaluationRecord rows and, on FAIL, triggers FindingsService
to create/update a Finding.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    ConfigurationVersionRecord,
    DeviceRecord,
    PolicyEvaluationRecord,
    PolicyRecord,
    ServiceObservationRecord,
    TelemetryRecord,
)
from policy import engine as policy_engine

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PolicyInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    severity: str = Field(pattern=r"^(critical|high|medium|low|info)$")
    vendor_scope: list[str] = Field(default_factory=list)
    device_type_scope: list[str] = Field(default_factory=list)
    rule_type: str = Field(pattern=r"^(config_pattern|telemetry_threshold|service_check|interface_check)$")
    rule_definition: dict = Field(default_factory=dict)
    enabled: bool = True

    model_config = {"extra": "forbid"}


class PolicyService:
    def __init__(self, session_factory, findings_service=None):
        self._session_factory = session_factory
        self._findings = findings_service

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list(self, category: str | None = None, severity: str | None = None,
             enabled: bool | None = None, vendor: str | None = None) -> list[dict]:
        with self._session_factory() as session:
            q = select(PolicyRecord)
            if category:
                q = q.where(PolicyRecord.category == category)
            if severity:
                q = q.where(PolicyRecord.severity == severity)
            if enabled is not None:
                q = q.where(PolicyRecord.enabled == enabled)
            q = q.order_by(PolicyRecord.severity, PolicyRecord.name)
            policies = list(session.scalars(q))
            return [self._serialize(p) for p in policies]

    def get(self, policy_id: str) -> dict:
        with self._session_factory() as session:
            record = session.get(PolicyRecord, policy_id)
            if not record:
                raise KeyError(policy_id)
            return self._serialize(record)

    def create(self, payload: PolicyInput, actor: str) -> dict:
        now = _utcnow()
        record = PolicyRecord(
            id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            category=payload.category,
            severity=payload.severity,
            vendor_scope=payload.vendor_scope,
            device_type_scope=payload.device_type_scope,
            rule_type=payload.rule_type,
            rule_definition=payload.rule_definition,
            enabled=payload.enabled,
            created_at=now,
            created_by=actor,
        )
        with self._session_factory() as session:
            session.add(record)
            try:
                session.commit()
                session.refresh(record)
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(f"policy name already exists: {payload.name}") from exc
        return self._serialize(record)

    def update(self, policy_id: str, payload: PolicyInput, actor: str) -> dict:
        with self._session_factory() as session:
            record = session.get(PolicyRecord, policy_id)
            if not record:
                raise KeyError(policy_id)
            record.name = payload.name
            record.description = payload.description
            record.category = payload.category
            record.severity = payload.severity
            record.vendor_scope = payload.vendor_scope
            record.device_type_scope = payload.device_type_scope
            record.rule_type = payload.rule_type
            record.rule_definition = payload.rule_definition
            record.enabled = payload.enabled
            record.updated_at = _utcnow()
            try:
                session.commit()
                session.refresh(record)
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(f"policy name conflict: {payload.name}") from exc
            return self._serialize(record)

    def delete(self, policy_id: str, actor: str) -> None:
        with self._session_factory() as session:
            record = session.get(PolicyRecord, policy_id)
            if not record:
                raise KeyError(policy_id)
            session.delete(record)
            session.commit()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_policy(self, policy_id: str, device_ids: list[str] | None = None) -> list[dict]:
        """
        Evaluate a single policy against all applicable devices (or a subset).
        Returns list of evaluation result dicts.
        """
        with self._session_factory() as session:
            policy = session.get(PolicyRecord, policy_id)
            if not policy:
                raise KeyError(policy_id)

            q = select(DeviceRecord)
            if device_ids:
                q = q.where(DeviceRecord.id.in_(device_ids))
            if policy.vendor_scope:
                q = q.where(DeviceRecord.vendor.in_(policy.vendor_scope))
            if policy.device_type_scope:
                q = q.where(DeviceRecord.type.in_(policy.device_type_scope))
            devices = list(session.scalars(q))

        results = []
        for device in devices:
            eval_result = self._evaluate_one(policy, device)
            results.append(eval_result)
        return results

    def _evaluate_one(self, policy: PolicyRecord, device: DeviceRecord) -> dict:
        now = _utcnow()
        context = self._build_context(policy, device)
        result, details = policy_engine.evaluate(policy, context)

        eval_id = str(uuid4())
        with self._session_factory() as session:
            # Get FK references if available
            latest_telemetry_id = None
            latest_config_id = None
            if context.get("telemetry_id"):
                latest_telemetry_id = context["telemetry_id"]
            if context.get("config_version_id"):
                latest_config_id = context["config_version_id"]

            eval_rec = PolicyEvaluationRecord(
                id=eval_id,
                policy_id=policy.id,
                device_id=device.id,
                evaluated_at=now,
                result=result,
                details=details,
                telemetry_id=latest_telemetry_id,
                config_version_id=latest_config_id,
            )
            session.add(eval_rec)
            session.commit()

        # On FAIL, create/update a Finding
        if result == policy_engine.FAIL and self._findings:
            try:
                self._findings.record_finding(
                    device_id=device.id,
                    policy_id=policy.id,
                    severity=policy.severity,
                    title=f"Policy violation: {policy.name}",
                    description=details.get("reason", ""),
                    category=policy.category,
                    evidence_refs=[eval_id],
                )
            except Exception:
                log.exception("failed to record finding for policy %s device %s", policy.id, device.id)

        return {
            "evaluation_id": eval_id,
            "policy_id": policy.id,
            "policy_name": policy.name,
            "device_id": device.id,
            "device_name": device.name,
            "evaluated_at": now,
            "result": result,
            "details": details,
        }

    def _build_context(self, policy: PolicyRecord, device: DeviceRecord) -> dict:
        """Assemble evaluation context from latest stored data — no live device calls."""
        context: dict = {}

        with self._session_factory() as session:
            if policy.rule_type == "config_pattern":
                latest_ver = session.scalar(
                    select(ConfigurationVersionRecord)
                    .where(
                        ConfigurationVersionRecord.device_id == device.id,
                        ConfigurationVersionRecord.retention_state == "active",
                    )
                    .order_by(ConfigurationVersionRecord.collected_at.desc())
                    .limit(1)
                )
                if latest_ver:
                    context["config_version_id"] = latest_ver.id
                    try:
                        from configuration.service import ConfigurationService
                        from storage.local import LocalArtifactStorage
                        from config import load_config
                        cfg_svc = ConfigurationService(LocalArtifactStorage(load_config().backup_root))
                        context["config_text"] = cfg_svc.content(latest_ver)
                    except Exception:
                        pass

            elif policy.rule_type == "telemetry_threshold":
                latest_tel = session.scalar(
                    select(TelemetryRecord)
                    .where(TelemetryRecord.device_id == device.id)
                    .order_by(TelemetryRecord.collected_at.desc())
                    .limit(1)
                )
                if latest_tel:
                    context["telemetry_id"] = latest_tel.id
                    context["telemetry"] = {
                        "cpu_percent": latest_tel.cpu_percent,
                        "memory_percent": latest_tel.memory_percent,
                        "temperature_c": latest_tel.temperature_c,
                        "fan_speed_rpm": latest_tel.fan_speed_rpm,
                    }

            elif policy.rule_type == "service_check":
                svc_rows = list(session.scalars(
                    select(ServiceObservationRecord)
                    .where(ServiceObservationRecord.device_id == device.id)
                    .order_by(ServiceObservationRecord.observed_at.desc())
                    .limit(50)
                ))
                context["services"] = [
                    {"port": s.port, "protocol": s.protocol, "state": s.state}
                    for s in svc_rows
                ]

            elif policy.rule_type == "interface_check":
                # Interfaces are in the device relationship
                dev_full = session.get(DeviceRecord, device.id)
                if dev_full and dev_full.interfaces:
                    context["interfaces"] = [
                        {
                            "name": i.name,
                            "admin_state": i.admin_state,
                            "operational_state": i.operational_state,
                            "addresses": i.addresses,
                            "description": i.description,
                        }
                        for i in dev_full.interfaces
                    ]

        return context

    @staticmethod
    def _serialize(record: PolicyRecord) -> dict:
        return {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "category": record.category,
            "severity": record.severity,
            "vendor_scope": record.vendor_scope,
            "device_type_scope": record.device_type_scope,
            "rule_type": record.rule_type,
            "rule_definition": record.rule_definition,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "created_by": record.created_by,
        }
