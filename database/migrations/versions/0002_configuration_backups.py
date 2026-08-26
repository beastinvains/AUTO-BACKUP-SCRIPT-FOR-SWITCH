"""create Phase 2 configuration backup metadata

Revision ID: 0002_configuration_backups
Revises: 0001_inventory
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_configuration_backups"
down_revision = "0001_inventory"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("configuration_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("parent_version_id", sa.String(36), sa.ForeignKey("configuration_versions.id")),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("storage_uri", sa.String(1024), nullable=False, unique=True),
        sa.Column("source_adapter", sa.String(100), nullable=False), sa.Column("platform", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("retention_state", sa.String(30), nullable=False))
    op.create_table("backup_jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("requested_by", sa.String(255), nullable=False), sa.Column("target_scope", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("status", sa.String(30), nullable=False), sa.Column("success_count", sa.Integer(), nullable=False), sa.Column("failure_count", sa.Integer(), nullable=False), sa.Column("results", sa.JSON(), nullable=False))
    op.create_table("audit_logs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("actor", sa.String(255), nullable=False), sa.Column("action", sa.String(100), nullable=False), sa.Column("resource_type", sa.String(100), nullable=False), sa.Column("resource_id", sa.String(255), nullable=False), sa.Column("correlation_id", sa.String(36), nullable=False), sa.Column("result", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("details", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("backup_jobs")
    op.drop_table("configuration_versions")
