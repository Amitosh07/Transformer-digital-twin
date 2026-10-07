"""initial canonical telemetry database

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: native JSONB, TIMESTAMPTZ, CHECKs, foreign keys and descending indexes.
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("parse_error_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("out_of_range_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("missing_count_by_field", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp_gap_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')", name=op.f("ck_ingestion_runs_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_table(
        "transformers",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rated_power_kva", sa.Float(), nullable=True),
        sa.Column("rated_voltage_hv", sa.Float(), nullable=True),
        sa.Column("rated_voltage_lv", sa.Float(), nullable=True),
        sa.Column("rated_current_a", sa.Float(), nullable=True),
        sa.Column("cooling_class", sa.String(length=128), nullable=True),
        sa.Column("oil_type", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transformers")),
    )
    op.create_table(
        "telemetry",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("transformer_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phase_voltage_l1", sa.Float(), nullable=True),
        sa.Column("phase_voltage_l2", sa.Float(), nullable=True),
        sa.Column("phase_voltage_l3", sa.Float(), nullable=True),
        sa.Column("current_l1", sa.Float(), nullable=True),
        sa.Column("current_l2", sa.Float(), nullable=True),
        sa.Column("current_l3", sa.Float(), nullable=True),
        sa.Column("neutral_current", sa.Float(), nullable=True),
        sa.Column("oil_temperature", sa.Float(), nullable=True),
        sa.Column("winding_temperature", sa.Float(), nullable=True),
        sa.Column("ambient_temperature", sa.Float(), nullable=True),
        sa.Column("oil_level", sa.Float(), nullable=True),
        sa.Column("active_power_total", sa.Float(), nullable=True),
        sa.Column("apparent_power_total", sa.Float(), nullable=True),
        sa.Column("reactive_power_total", sa.Float(), nullable=True),
        sa.Column("energy_kwh", sa.Float(), nullable=True),
        sa.Column("power_factor_l1", sa.Float(), nullable=True),
        sa.Column("power_factor_l2", sa.Float(), nullable=True),
        sa.Column("power_factor_l3", sa.Float(), nullable=True),
        sa.Column("oil_temp_alarm", sa.SmallInteger(), nullable=True),
        sa.Column("oil_temp_trip", sa.SmallInteger(), nullable=True),
        sa.Column("magnetic_oil_gauge_alarm", sa.SmallInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("scenario_id", sa.String(length=255), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "is_missing_critical", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("data_quality_score", sa.Float(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "magnetic_oil_gauge_alarm IN (0, 1)",
            name=op.f("ck_telemetry_magnetic_oil_gauge_alarm_binary"),
        ),
        sa.CheckConstraint(
            "oil_temp_alarm IN (0, 1)", name=op.f("ck_telemetry_oil_temp_alarm_binary")
        ),
        sa.CheckConstraint(
            "oil_temp_trip IN (0, 1)", name=op.f("ck_telemetry_oil_temp_trip_binary")
        ),
        sa.ForeignKeyConstraint(
            ["transformer_id"],
            ["transformers.id"],
            name=op.f("fk_telemetry_transformer_id_transformers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telemetry")),
        sa.UniqueConstraint(
            "transformer_id", "timestamp", name=op.f("uq_telemetry_transformer_id")
        ),
    )
    op.create_index(
        "ix_telemetry_transformer_timestamp_desc",
        "telemetry",
        ["transformer_id", sa.literal_column("timestamp DESC")],
        unique=False,
    )
    op.create_table(
        "analytics",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("telemetry_id", sa.BigInteger(), nullable=False),
        sa.Column("transformer_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inference_status", sa.String(length=32), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "missing_features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("loading_percent", sa.Float(), nullable=True),
        sa.Column("thermal_model_temperature", sa.Float(), nullable=True),
        sa.Column("thermal_residual", sa.Float(), nullable=True),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("health_index", sa.Float(), nullable=True),
        sa.Column("fault_risk", sa.Float(), nullable=True),
        sa.Column("prediction_confidence", sa.Float(), nullable=True),
        sa.Column("anomaly_flag", sa.Boolean(), nullable=True),
        sa.Column("thermal_state", sa.String(length=64), nullable=True),
        sa.Column("predicted_fault", sa.String(length=64), nullable=True),
        sa.Column("maintenance_priority", sa.String(length=64), nullable=True),
        sa.Column("maintenance_recommendation", sa.Text(), nullable=True),
        sa.Column("health_components", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("health_reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "inference_status IN ('OK', 'INSUFFICIENT_DATA')",
            name=op.f("ck_analytics_inference_status"),
        ),
        sa.CheckConstraint(
            "maintenance_priority IN ('NORMAL', 'WATCH', 'PLAN', 'URGENT')",
            name=op.f("ck_analytics_maintenance_priority"),
        ),
        sa.CheckConstraint(
            "anomaly_score >= 0 AND anomaly_score <= 1",
            name=op.f("ck_analytics_anomaly_score_range"),
        ),
        sa.CheckConstraint(
            "fault_risk >= 0 AND fault_risk <= 1", name=op.f("ck_analytics_fault_risk_range")
        ),
        sa.CheckConstraint(
            "health_index >= 0 AND health_index <= 100",
            name=op.f("ck_analytics_health_index_range"),
        ),
        sa.CheckConstraint(
            "prediction_confidence >= 0 AND prediction_confidence <= 1",
            name=op.f("ck_analytics_prediction_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["telemetry_id"], ["telemetry.id"], name=op.f("fk_analytics_telemetry_id_telemetry")
        ),
        sa.ForeignKeyConstraint(
            ["transformer_id"],
            ["transformers.id"],
            name=op.f("fk_analytics_transformer_id_transformers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics")),
        sa.UniqueConstraint("telemetry_id", name=op.f("uq_analytics_telemetry_id")),
    )
    op.create_index(
        "ix_analytics_transformer_timestamp_desc",
        "analytics",
        ["transformer_id", sa.literal_column("timestamp DESC")],
        unique=False,
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("transformer_id", sa.String(length=128), nullable=False),
        sa.Column("analytics_id", sa.BigInteger(), nullable=True),
        sa.Column("telemetry_id", sa.BigInteger(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=128), nullable=False),
        sa.Column("alert_type", sa.String(length=128), nullable=False),
        sa.Column("trigger", sa.String(length=128), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("threshold_or_reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')", name=op.f("ck_alerts_severity")
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')", name=op.f("ck_alerts_status")
        ),
        sa.ForeignKeyConstraint(
            ["analytics_id"], ["analytics.id"], name=op.f("fk_alerts_analytics_id_analytics")
        ),
        sa.ForeignKeyConstraint(
            ["telemetry_id"], ["telemetry.id"], name=op.f("fk_alerts_telemetry_id_telemetry")
        ),
        sa.ForeignKeyConstraint(
            ["transformer_id"],
            ["transformers.id"],
            name=op.f("fk_alerts_transformer_id_transformers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index("ix_alerts_status", "alerts", ["status"], unique=False)
    op.create_index(
        "ix_alerts_transformer_timestamp_desc",
        "alerts",
        ["transformer_id", sa.literal_column("timestamp DESC")],
        unique=False,
    )
    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("transformer_id", sa.String(length=128), nullable=False),
        sa.Column("analytics_id", sa.BigInteger(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority IN ('NORMAL', 'WATCH', 'PLAN', 'URGENT')",
            name=op.f("ck_maintenance_records_priority"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'DONE', 'DISMISSED')", name=op.f("ck_maintenance_records_status")
        ),
        sa.ForeignKeyConstraint(
            ["analytics_id"],
            ["analytics.id"],
            name=op.f("fk_maintenance_records_analytics_id_analytics"),
        ),
        sa.ForeignKeyConstraint(
            ["transformer_id"],
            ["transformers.id"],
            name=op.f("fk_maintenance_records_transformer_id_transformers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_maintenance_records")),
    )


def downgrade() -> None:
    # Reviewed: native JSONB, TIMESTAMPTZ, CHECKs, foreign keys and descending indexes.
    op.drop_table("maintenance_records")
    op.drop_index("ix_alerts_transformer_timestamp_desc", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_analytics_transformer_timestamp_desc", table_name="analytics")
    op.drop_table("analytics")
    op.drop_index("ix_telemetry_transformer_timestamp_desc", table_name="telemetry")
    op.drop_table("telemetry")
    op.drop_table("transformers")
    op.drop_table("ingestion_runs")
