"""Canonical input validation shared by future ingestion entry points."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class TelemetryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    transformer_id: str = Field(min_length=1, max_length=128)
    timestamp: AwareDatetime
    phase_voltage_l1: float | None = Field(default=None, strict=True)
    phase_voltage_l2: float | None = Field(default=None, strict=True)
    phase_voltage_l3: float | None = Field(default=None, strict=True)
    current_l1: float | None = Field(default=None, strict=True)
    current_l2: float | None = Field(default=None, strict=True)
    current_l3: float | None = Field(default=None, strict=True)
    neutral_current: float | None = Field(default=None, strict=True)
    oil_temperature: float | None = Field(default=None, strict=True)
    winding_temperature: float | None = Field(default=None, strict=True)
    ambient_temperature: float | None = Field(default=None, strict=True)
    oil_level: float | None = Field(default=None, strict=True)
    active_power_total: float | None = Field(default=None, strict=True)
    apparent_power_total: float | None = Field(default=None, strict=True)
    reactive_power_total: float | None = Field(default=None, strict=True)
    energy_kwh: float | None = Field(default=None, strict=True)
    power_factor_l1: float | None = Field(default=None, strict=True)
    power_factor_l2: float | None = Field(default=None, strict=True)
    power_factor_l3: float | None = Field(default=None, strict=True)
    oil_temp_alarm: Literal[0, 1] | None = None
    oil_temp_trip: Literal[0, 1] | None = None
    magnetic_oil_gauge_alarm: Literal[0, 1] | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def require_datetime_input(cls, value: object) -> object:
        if not isinstance(value, (str, datetime)):
            raise ValueError("Timestamp must be an ISO-8601 string or aware datetime")
        return value

    @field_validator("timestamp")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm", mode="before")
    @classmethod
    def binary_protection(cls, value: object) -> object:
        if value is None:
            return None
        if type(value) not in (int, bool) or value not in (0, 1):
            raise ValueError("Protection fields require 0, 1, true, false, or null")
        return int(value)
