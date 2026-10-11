"""Add H00 provenance/configuration, durable receipts and H01 checkpoints.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

ASSET_COLUMNS = {
    'rated_frequency_hz': sa.Float(), 'vector_group': sa.String(128),
    'impedance_percent': sa.Float(), 'temperature_rise_limits': JSONB(none_as_null=True),
    'measurement_side': sa.String(16), 'ct_ratio': JSONB(none_as_null=True),
    'pt_ratio': JSONB(none_as_null=True), 'insulation_type': sa.String(128),
    'loss_parameters': JSONB(none_as_null=True), 'configuration_metadata': JSONB(none_as_null=True)}
TELEMETRY_COLUMNS = {'acquisition': JSONB(none_as_null=True), 'payload_hash': sa.String(64),
    'semantic_payload': sa.Text(), 'ingestion_outcome': sa.String(32),
    'ml_status': sa.String(64), 'ml_error': sa.String(128)}


def upgrade():
    op.add_column('transformers', sa.Column('schema_version', sa.String(64), nullable=False, server_default='1.0.0'))
    for table, columns in (('transformers', ASSET_COLUMNS), ('telemetry', TELEMETRY_COLUMNS),
                           ('analytics', {'metadata': JSONB(none_as_null=True), 'rul': JSONB(none_as_null=True)})):
        for name, type_ in columns.items():
            op.add_column(table, sa.Column(name, type_, nullable=True))
    op.create_table('ingestion_receipts',
        sa.Column('snapshot_id', sa.String(64), primary_key=True),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('transformer_id', sa.String(128), sa.ForeignKey('transformers.id'), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('telemetry_id', sa.BigInteger(), sa.ForeignKey('telemetry.id'), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('ingestion_outcome', sa.String(32), nullable=False),
        sa.Column('ml_status', sa.String(64), nullable=True),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reason', sa.String(128), nullable=True))
    op.add_column('ingestion_receipts', sa.Column('accepted_payload_hash', sa.String(64), nullable=False))
    op.add_column('ingestion_receipts', sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('ml_checkpoints',
        sa.Column('transformer_id', sa.String(128), sa.ForeignKey('transformers.id'), primary_key=True),
        sa.Column('checkpoint', JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table('ml_checkpoints')
    op.drop_table('ingestion_receipts')
    for table, columns in (('analytics', {'metadata': None, 'rul': None}),
                           ('telemetry', TELEMETRY_COLUMNS), ('transformers', ASSET_COLUMNS)):
        for name in reversed(list(columns)):
            op.drop_column(table, name)
    op.drop_column('transformers', 'schema_version')
