from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Analytics(Base):
    """Fault risk and predicted fault describe proxy alarm/trip targets."""

    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telemetry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("telemetry.id"), unique=True)
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey("transformers.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inference_status: Mapped[str] = mapped_column(String(32))
    error_detail: Mapped[str | None] = mapped_column(Text)
    missing_features: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    loading_percent: Mapped[float | None] = mapped_column(Float)
    thermal_model_temperature: Mapped[float | None] = mapped_column(Float)
    thermal_residual: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    health_index: Mapped[float | None] = mapped_column(Float)
    fault_risk: Mapped[float | None] = mapped_column(Float)
    prediction_confidence: Mapped[float | None] = mapped_column(Float)
    anomaly_flag: Mapped[bool | None] = mapped_column(Boolean)
    thermal_state: Mapped[str | None] = mapped_column(String(64))
    predicted_fault: Mapped[str | None] = mapped_column(String(64))
    maintenance_priority: Mapped[str | None] = mapped_column(String(64))
    maintenance_recommendation: Mapped[str | None] = mapped_column(Text)
    health_components: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    health_reason_codes: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    reason_codes: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    ml_metadata: Mapped[dict[str, Any] | None] = mapped_column('metadata', JSONB(none_as_null=True))
    rul: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    schema_version: Mapped[str] = mapped_column(String(64))
    feature_version: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("anomaly_score >= 0 AND anomaly_score <= 1", name="anomaly_score_range"),
        CheckConstraint("fault_risk >= 0 AND fault_risk <= 1", name="fault_risk_range"),
        CheckConstraint(
            "prediction_confidence >= 0 AND prediction_confidence <= 1",
            name="prediction_confidence_range",
        ),
        CheckConstraint("health_index >= 0 AND health_index <= 100", name="health_index_range"),
        CheckConstraint("inference_status IN ('OK', 'INSUFFICIENT_DATA')", name="inference_status"),
        CheckConstraint(
            "maintenance_priority IN ('NORMAL', 'WATCH', 'PLAN', 'URGENT')",
            name="maintenance_priority",
        ),
        Index("ix_analytics_transformer_timestamp_desc", transformer_id, timestamp.desc()),
    )
