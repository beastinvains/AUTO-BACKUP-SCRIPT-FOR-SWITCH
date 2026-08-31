from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class DeviceRecord(Base):
    __tablename__ = "devices"
    # A device is identified by the management endpoint it is reached on, not by address alone:
    # several logical devices can legitimately share one address on different SSH ports (lab
    # estates, jump hosts, port-forwarded appliances). This is the same reasoning that made
    # management_port a persisted column in 0003_device_ssh_port.
    __table_args__ = (UniqueConstraint("management_ip", "management_port", name="uq_devices_management_endpoint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50))
    vendor: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    management_ip: Mapped[str] = mapped_column(String(45), index=True)
    management_port: Mapped[int] = mapped_column(Integer, default=22, server_default="22")
    credentials_reference_id: Mapped[str] = mapped_column(String(255))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50))
    site: Mapped[str | None] = mapped_column(String(255))
    discovery_state: Mapped[str] = mapped_column(String(50))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    interfaces: Mapped[list["InterfaceRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    neighbors: Mapped[list["NeighborRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    health: Mapped["HealthRecord | None"] = relationship(back_populates="device", cascade="all, delete-orphan", uselist=False)
    configuration_versions: Mapped[list["ConfigurationVersionRecord"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class InterfaceRecord(Base):
    __tablename__ = "interfaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    name: Mapped[str] = mapped_column(String(255))
    admin_state: Mapped[str] = mapped_column(String(50))
    operational_state: Mapped[str] = mapped_column(String(50))
    addresses: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    speed: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[DeviceRecord] = relationship(back_populates="interfaces")


class NeighborRecord(Base):
    __tablename__ = "neighbors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    local_interface: Mapped[str] = mapped_column(String(255))
    remote_system_name: Mapped[str | None] = mapped_column(String(255))
    remote_interface: Mapped[str | None] = mapped_column(String(255))
    remote_chassis_id: Mapped[str | None] = mapped_column(String(255))
    device: Mapped[DeviceRecord] = relationship(back_populates="neighbors")


class HealthRecord(Base):
    __tablename__ = "health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), unique=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    memory_percent: Mapped[float | None] = mapped_column(Float)
    uptime: Mapped[str | None] = mapped_column(String(255))
    hardware_status: Mapped[str] = mapped_column(String(50))
    temperature_c: Mapped[float | None] = mapped_column(Float)
    fan_speed_rpm: Mapped[int | None] = mapped_column(Integer)
    power_supplies: Mapped[list] = mapped_column(JSON, default=list)
    cluster_members: Mapped[list] = mapped_column(JSON, default=list)
    device: Mapped[DeviceRecord] = relationship(back_populates="health")


class ConfigurationVersionRecord(Base):
    __tablename__ = "configuration_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_versions.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_uri: Mapped[str] = mapped_column(String(1024), unique=True)
    source_adapter: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(100))
    parser_version: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    retention_state: Mapped[str] = mapped_column(String(30), default="active")
    device: Mapped[DeviceRecord] = relationship(back_populates="configuration_versions")


class BackupJobRecord(Base):
    __tablename__ = "backup_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requested_by: Mapped[str] = mapped_column(String(255))
    target_scope: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[list] = mapped_column(JSON, default=list)


class ScheduleRecord(Base):
    """A recurring backup window. Execution always goes through BackupService."""

    __tablename__ = "backup_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    device_ids: Mapped[list] = mapped_column(JSON, default=list)  # empty list means every device
    frequency: Mapped[str] = mapped_column(String(20))
    run_at: Mapped[str] = mapped_column(String(5))  # HH:MM, UTC
    day_of_week: Mapped[int | None] = mapped_column(Integer)  # 0=Monday, weekly only
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(30))
    last_job_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(255))
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    result: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


# ---------------------------------------------------------------------------
# Phase 4 — Continuous Security Monitoring, Policy Engine, Findings & Evidence
# ---------------------------------------------------------------------------

class MonitoringJobRecord(Base):
    """Tracks a single fan-out monitoring collection run across all/selected devices."""
    __tablename__ = "monitoring_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(30), index=True)  # pending|running|success|partial|failed
    kind: Mapped[str] = mapped_column(String(30))  # telemetry|service|interface|drift
    device_ids: Mapped[list] = mapped_column(JSON, default=list)  # empty = all devices
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_by: Mapped[str] = mapped_column(String(30))  # scheduled|manual|drift
    collection_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    telemetry_records: Mapped[list["TelemetryRecord"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    service_observations: Mapped[list["ServiceObservationRecord"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class EvidenceRecord(Base):
    """
    Immutable evidence artifact record — separate from configuration backup artifacts.
    The content lives in LocalArtifactStorage; this row holds the metadata + SHA-256.
    """
    __tablename__ = "evidence_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), index=True)
    collection_job_id: Mapped[str | None] = mapped_column(ForeignKey("monitoring_jobs.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # evidence_type controls how this record is read and stored:
    # configuration_snapshot|telemetry|interface_state|service_exposure|
    # topology_observation|compliance_result|finding|report
    evidence_type: Mapped[str] = mapped_column(String(50), index=True)
    source_adapter: Mapped[str | None] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_uri: Mapped[str] = mapped_column(String(1024), unique=True)
    config_version_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_versions.id"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    device: Mapped["DeviceRecord | None"] = relationship()


class TelemetryRecord(Base):
    """
    One normalized telemetry snapshot per device per monitoring job.
    Reachability + hardware health captured here so the policy engine and UI
    can read structured values without parsing raw command output.
    """
    __tablename__ = "telemetry_records"
    __table_args__ = (
        Index("ix_telemetry_device_collected", "device_id", "collected_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    collection_job_id: Mapped[str] = mapped_column(ForeignKey("monitoring_jobs.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    memory_percent: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    fan_speed_rpm: Mapped[int | None] = mapped_column(Integer)
    power_status: Mapped[str | None] = mapped_column(String(30))  # ok|degraded|failed|unknown
    reachability: Mapped[str] = mapped_column(String(30))  # online|timeout|error|unknown
    interface_summary: Mapped[dict] = mapped_column(JSON, default=dict)  # {total, up, down, errors}
    raw_evidence_ref: Mapped[str | None] = mapped_column(ForeignKey("evidence_records.id"))
    device: Mapped["DeviceRecord"] = relationship()
    job: Mapped["MonitoringJobRecord"] = relationship(back_populates="telemetry_records")


class ServiceObservationRecord(Base):
    """
    One observed listening port/service per device per collection job.
    Used by the policy engine to detect policy-disallowed services.
    """
    __tablename__ = "service_observations"
    __table_args__ = (
        Index("ix_service_device_port", "device_id", "port", "protocol"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    collection_job_id: Mapped[str] = mapped_column(ForeignKey("monitoring_jobs.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(10))  # tcp|udp
    service_name: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20))  # open|closed|filtered|unknown
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_evidence_ref: Mapped[str | None] = mapped_column(ForeignKey("evidence_records.id"))
    device: Mapped["DeviceRecord"] = relationship()
    job: Mapped["MonitoringJobRecord"] = relationship(back_populates="service_observations")


class PolicyRecord(Base):
    """
    Admin-defined, deterministic security policy rule.
    No LLM involved — rule_definition contains structured parameters only.
    """
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), index=True)  # access_control|hardening|availability|...
    severity: Mapped[str] = mapped_column(String(20), index=True)  # critical|high|medium|low|info
    # Scope filters — empty list = applies to all
    vendor_scope: Mapped[list] = mapped_column(JSON, default=list)
    device_type_scope: Mapped[list] = mapped_column(JSON, default=list)
    # rule_type: config_pattern|telemetry_threshold|service_check|interface_check
    rule_type: Mapped[str] = mapped_column(String(50))
    # rule_definition: deterministic parameters; schema varies by rule_type
    rule_definition: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255))
    evaluations: Mapped[list["PolicyEvaluationRecord"]] = relationship(back_populates="policy", cascade="all, delete-orphan")
    findings: Mapped[list["FindingRecord"]] = relationship(back_populates="policy")


class PolicyEvaluationRecord(Base):
    """Result of evaluating one policy against one device at one point in time."""
    __tablename__ = "policy_evaluations"
    __table_args__ = (
        Index("ix_eval_policy_device_time", "policy_id", "device_id", "evaluated_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    result: Mapped[str] = mapped_column(String(20), index=True)  # pass|fail|unknown
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)  # list of evidence_record.id
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # human-readable context
    config_version_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_versions.id"))
    telemetry_id: Mapped[str | None] = mapped_column(ForeignKey("telemetry_records.id"))
    policy: Mapped["PolicyRecord"] = relationship(back_populates="evaluations")
    device: Mapped["DeviceRecord"] = relationship()


class FindingRecord(Base):
    """
    Deduplicated security finding.
    When an existing open finding with (device_id, policy_id, title) is seen again,
    occurrence_count is incremented and last_seen_at is updated — no new row.
    """
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_finding_device_policy", "device_id", "policy_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)  # open|acknowledged|resolved|suppressed
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    related_config_version_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_versions.id"))
    related_telemetry_id: Mapped[str | None] = mapped_column(ForeignKey("telemetry_records.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    device: Mapped["DeviceRecord"] = relationship()
    policy: Mapped["PolicyRecord | None"] = relationship(back_populates="findings")
    alerts: Mapped[list["AlertRecord"]] = relationship(back_populates="finding", cascade="all, delete-orphan")


class AlertRecord(Base):
    """
    Alert generated from a finding or a direct monitoring event.
    Never duplicate an identical open alert — re-use and update existing.
    """
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), index=True)
    # category matches the alert taxonomy from the spec
    category: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)  # new|acknowledged|resolved
    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str | None] = mapped_column(String(255))
    evidence_ref: Mapped[str | None] = mapped_column(ForeignKey("evidence_records.id"))
    device: Mapped["DeviceRecord | None"] = relationship()
    finding: Mapped["FindingRecord | None"] = relationship(back_populates="alerts")


class SecurityReportRecord(Base):
    """
    A reproducible security assessment report built entirely from stored evidence.
    device_id = NULL for estate-wide reports.
    """
    __tablename__ = "security_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    generated_by: Mapped[str] = mapped_column(String(255))
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    storage_uri: Mapped[str | None] = mapped_column(String(1024), unique=True)
    compliance_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    findings_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    telemetry_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    service_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    device: Mapped["DeviceRecord | None"] = relationship()

