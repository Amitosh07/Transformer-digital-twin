from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    parse_error_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    out_of_range_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    missing_count_by_field: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    timestamp_gap_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    schema_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint("status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="status"),
    )
