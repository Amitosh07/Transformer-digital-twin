from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Any

from app.db.base import Base


class Transformer(Base):
    __tablename__ = "transformers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    rated_power_kva: Mapped[float | None] = mapped_column(Float)
    rated_voltage_hv: Mapped[float | None] = mapped_column(Float)
    rated_voltage_lv: Mapped[float | None] = mapped_column(Float)
    rated_current_a: Mapped[float | None] = mapped_column(Float)
    cooling_class: Mapped[str | None] = mapped_column(String(128))
    oil_type: Mapped[str | None] = mapped_column(String(128))
    schema_version: Mapped[str] = mapped_column(String(64), server_default='1.0.0')
    rated_frequency_hz: Mapped[float | None] = mapped_column(Float)
    vector_group: Mapped[str | None] = mapped_column(String(128))
    impedance_percent: Mapped[float | None] = mapped_column(Float)
    temperature_rise_limits: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    measurement_side: Mapped[str | None] = mapped_column(String(16))
    ct_ratio: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    pt_ratio: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    insulation_type: Mapped[str | None] = mapped_column(String(128))
    loss_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    configuration_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
