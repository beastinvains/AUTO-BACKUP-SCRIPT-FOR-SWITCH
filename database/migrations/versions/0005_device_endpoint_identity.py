"""identify a device by management IP + SSH port, not by IP alone

Revision ID: 0005_device_endpoint_identity
Revises: 0004_backup_schedules

``0001_inventory`` made ``management_ip`` unique on its own, which was true only while
every device sat on port 22.  Since ``0003_device_ssh_port`` the connection target is the
pair, and several devices can legitimately share one address on different ports: a mock
lab on a single host, port-forwarded appliances behind a jump host, or an out-of-band
console server.  This replaces the single-column constraint with the pair.

The old constraint was created inline and therefore unnamed, so SQLite cannot drop it by
name — the table has to be recreated.  Other dialects name it automatically, so the name
is looked up through the inspector instead of guessed.

Downgrading requires the data to still satisfy the stricter rule: if two devices share an
address on different ports, the single-column unique constraint cannot be restored until
one of them is removed.  A downgrade that fails that way on SQLite leaves the batch's
``_alembic_tmp_devices`` table behind; drop it before retrying.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_device_endpoint_identity"
down_revision = "0004_backup_schedules"
branch_labels = None
depends_on = None

ENDPOINT_CONSTRAINT = "uq_devices_management_endpoint"
ADDRESS_INDEX = "ix_devices_management_ip"


def _devices_table(*, endpoint_unique: bool) -> sa.Table:
    """The ``devices`` table as SQLite must rebuild it.

    ``batch_alter_table(copy_from=...)`` recreates exactly what it is given, so this has to
    describe every column and every constraint that must survive the rebuild — including the
    unique name, which is unrelated to this change but would otherwise be silently dropped.
    """
    constraints = []
    if endpoint_unique:
        constraints.append(sa.UniqueConstraint("management_ip", "management_port", name=ENDPOINT_CONSTRAINT))
    return sa.Table(
        "devices", sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("vendor", sa.String(100)),
        sa.Column("model", sa.String(255)),
        sa.Column("platform", sa.String(100)),
        sa.Column("os_version", sa.String(255)),
        sa.Column("serial_number", sa.String(255)),
        sa.Column("management_ip", sa.String(45), nullable=False),
        sa.Column("management_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("credentials_reference_id", sa.String(255), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("site", sa.String(255)),
        sa.Column("discovery_state", sa.String(50), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        *constraints,
    )


def _unique_names_on(bind, columns: list[str]) -> list[str]:
    """Names of unique constraints/indexes covering exactly ``columns``."""
    inspector = sa.inspect(bind)
    found = []
    for constraint in inspector.get_unique_constraints("devices"):
        if list(constraint.get("column_names") or []) == columns and constraint.get("name"):
            found.append(constraint["name"])
    for index in inspector.get_indexes("devices"):
        name = index.get("name")
        if index.get("unique") and list(index.get("column_names") or []) == columns and name and name not in found:
            found.append(name)
    return found


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("devices", copy_from=_devices_table(endpoint_unique=False),
                                  recreate="always") as batch:
            batch.create_unique_constraint(ENDPOINT_CONSTRAINT, ["management_ip", "management_port"])
            batch.create_index(ADDRESS_INDEX, ["management_ip"])
        return
    for name in _unique_names_on(bind, ["management_ip"]):
        op.drop_constraint(name, "devices", type_="unique")
    op.create_unique_constraint(ENDPOINT_CONSTRAINT, "devices", ["management_ip", "management_port"])
    op.create_index(ADDRESS_INDEX, "devices", ["management_ip"])


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("devices", copy_from=_devices_table(endpoint_unique=True),
                                  recreate="always") as batch:
            batch.drop_constraint(ENDPOINT_CONSTRAINT, type_="unique")
            batch.create_unique_constraint("uq_devices_management_ip", ["management_ip"])
        return
    op.drop_index(ADDRESS_INDEX, table_name="devices")
    op.drop_constraint(ENDPOINT_CONSTRAINT, "devices", type_="unique")
    op.create_unique_constraint("uq_devices_management_ip", "devices", ["management_ip"])
