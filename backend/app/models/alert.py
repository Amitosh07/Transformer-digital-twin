from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey("transformers.id"))
    analytics_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("analytics.id"))
    telemetry_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("telemetry.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(128))
    alert_type: Mapped[str] = mapped_column(String(128))
    trigger: Mapped[str] = mapped_column(String(128))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True))
    threshold_or_reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), server_default=text("'OPEN'"))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    clear_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_alerts_active_transformer_type",
            transformer_id,
            alert_type,
            unique=True,
            postgresql_where=status.in_(["OPEN", "ACKNOWLEDGED"]),
        ),
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
        CheckConstraint("status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')", name="status"),
        Index("ix_alerts_transformer_timestamp_desc", transformer_id, timestamp.desc()),
        Index("ix_alerts_status", status),
    )
