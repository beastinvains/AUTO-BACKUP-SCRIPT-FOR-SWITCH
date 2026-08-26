"""persist per-device SSH management port

Revision ID: 0003_device_ssh_port
Revises: 0002_configuration_backups

Backups rebuild the device connection target from the stored inventory row, so the
SSH port used at discovery must be persisted; otherwise every backup falls back to
port 22 and cannot reach devices on non-standard ports.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_device_ssh_port"
down_revision = "0002_configuration_backups"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("devices", sa.Column("management_port", sa.Integer(), nullable=False, server_default="22"))


def downgrade():
    op.drop_column("devices", "management_port")
