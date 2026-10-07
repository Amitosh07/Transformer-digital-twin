from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey("transformers.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase_voltage_l1: Mapped[float | None] = mapped_column(Float)
    phase_voltage_l2: Mapped[float | None] = mapped_column(Float)
    phase_voltage_l3: Mapped[float | None] = mapped_column(Float)
    current_l1: Mapped[float | None] = mapped_column(Float)
    current_l2: Mapped[float | None] = mapped_column(Float)
    current_l3: Mapped[float | None] = mapped_column(Float)
    neutral_current: Mapped[float | None] = mapped_column(Float)
    oil_temperature: Mapped[float | None] = mapped_column(Float)
    winding_temperature: Mapped[float | None] = mapped_column(Float)
    ambient_temperature: Mapped[float | None] = mapped_column(Float)
    oil_level: Mapped[float | None] = mapped_column(Float)
    active_power_total: Mapped[float | None] = mapped_column(Float)
    apparent_power_total: Mapped[float | None] = mapped_column(Float)
    reactive_power_total: Mapped[float | None] = mapped_column(Float)
    energy_kwh: Mapped[float | None] = mapped_column(Float)
    power_factor_l1: Mapped[float | None] = mapped_column(Float)
    power_factor_l2: Mapped[float | None] = mapped_column(Float)
    power_factor_l3: Mapped[float | None] = mapped_column(Float)
    oil_temp_alarm: Mapped[int | None] = mapped_column(SmallInteger)
    oil_temp_trip: Mapped[int | None] = mapped_column(SmallInteger)
    magnetic_oil_gauge_alarm: Mapped[int | None] = mapped_column(SmallInteger)
    source_name: Mapped[str | None] = mapped_column(String(255))
    scenario_id: Mapped[str | None] = mapped_column(String(255))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), default=False)
    is_missing_critical: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False
    )
    data_quality_score: Mapped[float | None] = mapped_column(Float)
    schema_version: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("oil_temp_alarm IN (0, 1)", name="oil_temp_alarm_binary"),
        CheckConstraint("oil_temp_trip IN (0, 1)", name="oil_temp_trip_binary"),
        CheckConstraint(
            "magnetic_oil_gauge_alarm IN (0, 1)", name="magnetic_oil_gauge_alarm_binary"
        ),
        UniqueConstraint("transformer_id", "timestamp"),
        Index("ix_telemetry_transformer_timestamp_desc", transformer_id, timestamp.desc()),
    )
