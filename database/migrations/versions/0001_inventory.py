"""create phase 1 inventory tables

Revision ID: 0001_inventory
Revises:
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_inventory"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("devices", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False, unique=True), sa.Column("type", sa.String(50), nullable=False), sa.Column("vendor", sa.String(100)), sa.Column("model", sa.String(255)), sa.Column("platform", sa.String(100)), sa.Column("os_version", sa.String(255)), sa.Column("serial_number", sa.String(255)), sa.Column("management_ip", sa.String(45), nullable=False, unique=True), sa.Column("credentials_reference_id", sa.String(255), nullable=False), sa.Column("capabilities", sa.JSON(), nullable=False), sa.Column("status", sa.String(50), nullable=False), sa.Column("site", sa.String(255)), sa.Column("discovery_state", sa.String(50), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False))
    for name, columns in {"interfaces": [sa.Column("id", sa.Integer(), primary_key=True), sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("admin_state", sa.String(50), nullable=False), sa.Column("operational_state", sa.String(50), nullable=False), sa.Column("addresses", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("speed", sa.String(100))], "neighbors": [sa.Column("id", sa.Integer(), primary_key=True), sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False), sa.Column("local_interface", sa.String(255), nullable=False), sa.Column("remote_system_name", sa.String(255)), sa.Column("remote_interface", sa.String(255)), sa.Column("remote_chassis_id", sa.String(255))], "health": [sa.Column("id", sa.Integer(), primary_key=True), sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False, unique=True), sa.Column("cpu_percent", sa.Float()), sa.Column("memory_percent", sa.Float()), sa.Column("uptime", sa.String(255)), sa.Column("hardware_status", sa.String(50), nullable=False)]}.items():
        op.create_table(name, *columns)


def downgrade():
    op.drop_table("health")
    op.drop_table("neighbors")
    op.drop_table("interfaces")
    op.drop_table("devices")

