from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
