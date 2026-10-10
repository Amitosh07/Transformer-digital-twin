"""Canonical telemetry contracts; metadata is separate from measurements."""

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.schemas.common import CanonicalModel, FiniteFloat, UtcDatetime


class TelemetryIn(CanonicalModel):
    transformer_id: str = Field(min_length=1, max_length=128)
    timestamp: UtcDatetime
    phase_voltage_l1: FiniteFloat | None = None
    phase_voltage_l2: FiniteFloat | None = None
    phase_voltage_l3: FiniteFloat | None = None
    current_l1: FiniteFloat | None = None
    current_l2: FiniteFloat | None = None
    current_l3: FiniteFloat | None = None
    neutral_current: FiniteFloat | None = None
    oil_temperature: FiniteFloat | None = None
    winding_temperature: FiniteFloat | None = None
    ambient_temperature: FiniteFloat | None = None
    oil_level: FiniteFloat | None = None
    oil_temp_alarm: Literal[0, 1] | None = None
    oil_temp_trip: Literal[0, 1] | None = None
    magnetic_oil_gauge_alarm: Literal[0, 1] | None = None
    active_power_total: FiniteFloat | None = None
    apparent_power_total: FiniteFloat | None = None
    reactive_power_total: FiniteFloat | None = None
    energy_kwh: FiniteFloat | None = None
    power_factor_l1: FiniteFloat | None = Field(default=None, ge=-1, le=1)
    power_factor_l2: FiniteFloat | None = Field(default=None, ge=-1, le=1)
    power_factor_l3: FiniteFloat | None = Field(default=None, ge=-1, le=1)
    source_name: str | None = Field(default=None, max_length=255)
    scenario_id: str | None = Field(default=None, max_length=255)

    @field_validator("oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm", mode="before")
    @classmethod
    def binary_protection(cls, value: object) -> object:
        if value is None:
            return None
        if type(value) not in (int, bool) or value not in (0, 1):
            raise ValueError("Protection fields require 0, 1, true, false, or null")
        return int(value)


class TelemetryOut(TelemetryIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_missing_critical: bool
    data_quality_score: FiniteFloat | None = None
    schema_version: str


class TelemetryBatchIn(CanonicalModel):
    records: list[TelemetryIn] = Field(strict=True)

    @field_validator("records", mode="before")
    @classmethod
    def enforce_batch_limit(cls, value: object) -> object:
        maximum = get_settings().max_batch_size
        if isinstance(value, (list, tuple)) and len(value) > maximum:
            raise ValueError(f"Batch cannot exceed MAX_BATCH_SIZE ({maximum}) records")
        return value


# Preserve Phase 1 imports while exposing the agreed Phase 2 name.
TelemetryInput = TelemetryIn
