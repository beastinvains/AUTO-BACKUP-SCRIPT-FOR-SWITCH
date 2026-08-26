"""backup schedules driven by the Phase 2 BackupService

Revision ID: 0004_backup_schedules
Revises: 0003_device_ssh_port

Phase 3 replaces the single hard-coded daily backup window with named schedules that
carry their own device scope and cadence.  The rows only describe *when* to run; the
run itself goes through BackupService, so there is one backup implementation.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_backup_schedules"
down_revision = "0003_device_ssh_port"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backup_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_ids", sa.JSON(), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("run_at", sa.String(5), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(30), nullable=True),
        sa.Column("last_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backup_schedules_name", "backup_schedules", ["name"], unique=True)
    op.create_index("ix_backup_schedules_next_run_at", "backup_schedules", ["next_run_at"])


def downgrade():
    op.drop_index("ix_backup_schedules_next_run_at", table_name="backup_schedules")
    op.drop_index("ix_backup_schedules_name", table_name="backup_schedules")
    op.drop_table("backup_schedules")
