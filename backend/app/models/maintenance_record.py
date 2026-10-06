from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey("transformers.id"))
    analytics_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("analytics.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(32))
    recommendation: Mapped[str] = mapped_column(Text)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB(none_as_null=True))
    status: Mapped[str] = mapped_column(String(32), server_default=text("'OPEN'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("priority IN ('NORMAL', 'WATCH', 'PLAN', 'URGENT')", name="priority"),
        CheckConstraint("status IN ('OPEN', 'DONE', 'DISMISSED')", name="status"),
    )
