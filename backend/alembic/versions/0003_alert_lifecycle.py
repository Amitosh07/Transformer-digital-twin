"""Track consecutive clear observations and enforce one active alert per type.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("clear_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("alerts", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "uq_alerts_active_transformer_type",
        "alerts",
        ["transformer_id", "alert_type"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN','ACKNOWLEDGED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_alerts_active_transformer_type", table_name="alerts")
    op.drop_column("alerts", "resolved_at")
    op.drop_column("alerts", "clear_count")
