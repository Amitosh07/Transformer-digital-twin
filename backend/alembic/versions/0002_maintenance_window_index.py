"""Index maintenance windows by transformer and timestamp.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_maintenance_records_transformer_timestamp_desc",
        "maintenance_records",
        ["transformer_id", sa.text("timestamp DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_maintenance_records_transformer_timestamp_desc", table_name="maintenance_records"
    )
