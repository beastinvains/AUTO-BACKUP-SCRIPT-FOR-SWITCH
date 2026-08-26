"""store discovered temperature, fan, PSU and cluster telemetry"""
from alembic import op
import sqlalchemy as sa

revision = "0006_health_telemetry"
down_revision = "0005_device_endpoint_identity"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("health", sa.Column("temperature_c", sa.Float(), nullable=True))
    op.add_column("health", sa.Column("fan_speed_rpm", sa.Integer(), nullable=True))
    op.add_column("health", sa.Column("power_supplies", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("health", sa.Column("cluster_members", sa.JSON(), nullable=False, server_default="[]"))

def downgrade():
    op.drop_column("health", "cluster_members")
    op.drop_column("health", "power_supplies")
    op.drop_column("health", "fan_speed_rpm")
    op.drop_column("health", "temperature_c")