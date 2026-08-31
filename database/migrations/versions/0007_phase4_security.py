"""Phase 4 — security monitoring, policy engine, findings, alerts and evidence"""
from alembic import op
import sqlalchemy as sa

revision = "0007_phase4_security"
down_revision = "0006_health_telemetry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitoring_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("device_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(30), nullable=False),
        sa.Column("collection_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=True, index=True),
        sa.Column("collection_job_id", sa.String(36), sa.ForeignKey("monitoring_jobs.id"), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("evidence_type", sa.String(50), nullable=False, index=True),
        sa.Column("source_adapter", sa.String(100), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False, index=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.String(1024), nullable=False, unique=True),
        sa.Column("config_version_id", sa.String(36), sa.ForeignKey("configuration_versions.id"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "telemetry_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("collection_job_id", sa.String(36), sa.ForeignKey("monitoring_jobs.id"), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("fan_speed_rpm", sa.Integer(), nullable=True),
        sa.Column("power_status", sa.String(30), nullable=True),
        sa.Column("reachability", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("interface_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("raw_evidence_ref", sa.String(36), sa.ForeignKey("evidence_records.id"), nullable=True),
    )
    op.create_index("ix_telemetry_device_collected", "telemetry_records", ["device_id", "collected_at"])

    op.create_table(
        "service_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("collection_job_id", sa.String(36), sa.ForeignKey("monitoring_jobs.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(10), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_evidence_ref", sa.String(36), sa.ForeignKey("evidence_records.id"), nullable=True),
    )
    op.create_index("ix_service_device_port", "service_observations", ["device_id", "port", "protocol"])

    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("vendor_scope", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("device_type_scope", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("rule_definition", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
    )

    op.create_table(
        "policy_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id"), nullable=False, index=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("result", sa.String(20), nullable=False, index=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("config_version_id", sa.String(36), sa.ForeignKey("configuration_versions.id"), nullable=True),
        sa.Column("telemetry_id", sa.String(36), sa.ForeignKey("telemetry_records.id"), nullable=True),
    )
    op.create_index("ix_eval_policy_device_time", "policy_evaluations", ["policy_id", "device_id", "evaluated_at"])

    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id"), nullable=True, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("related_config_version_id", sa.String(36), sa.ForeignKey("configuration_versions.id"), nullable=True),
        sa.Column("related_telemetry_id", sa.String(36), sa.ForeignKey("telemetry_records.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_finding_device_policy", "findings", ["device_id", "policy_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=True, index=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=True, index=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("evidence_ref", sa.String(36), sa.ForeignKey("evidence_records.id"), nullable=True),
    )

    op.create_table(
        "security_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=True, index=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("generated_by", sa.String(255), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("storage_uri", sa.String(1024), nullable=True, unique=True),
        sa.Column("compliance_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("findings_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("telemetry_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("service_summary", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade():
    op.drop_table("security_reports")
    op.drop_table("alerts")
    op.drop_index("ix_finding_device_policy", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_eval_policy_device_time", table_name="policy_evaluations")
    op.drop_table("policy_evaluations")
    op.drop_table("policies")
    op.drop_index("ix_service_device_port", table_name="service_observations")
    op.drop_table("service_observations")
    op.drop_index("ix_telemetry_device_collected", table_name="telemetry_records")
    op.drop_table("telemetry_records")
    op.drop_table("evidence_records")
    op.drop_table("monitoring_jobs")
