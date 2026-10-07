"""Bounded dashboard queries and public series points."""

from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.analytics import HealthComponents
from app.schemas.common import (
    CanonicalModel,
    FiniteFloat,
    MaintenancePriority,
    ReasonCode,
    UtcDatetime,
)
from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS
from app.schemas.telemetry import TelemetryOut

PROTECTION_FIELDS = ["oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm"]
TELEMETRY_FIELDS = CANONICAL_TELEMETRY_FIELDS + [
    "id",
    "source_name",
    "scenario_id",
    "is_missing_critical",
    "data_quality_score",
]
NUMERIC_SIGNALS = [name for name in CANONICAL_TELEMETRY_FIELDS[2:] if name not in PROTECTION_FIELDS]
ANALYTIC_SIGNALS = [
    "anomaly_score",
    "health_index",
    "fault_risk",
    "thermal_residual",
    "loading_percent",
]
TREND_SIGNALS = NUMERIC_SIGNALS + ANALYTIC_SIGNALS


class TimeWindow(CanonicalModel):
    from_time: UtcDatetime | None = None
    to_time: UtcDatetime | None = None
    anchor: Literal["latest", "now"] = "now"


class ResolvedWindow(CanonicalModel):
    start: UtcDatetime
    end: UtcDatetime


class Pagination(CanonicalModel):
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class TelemetryPoint(TelemetryOut):
    """Full Out shape, or a fields projection with timestamp always present."""

    transformer_id: str | None = None
    id: int | None = None
    is_missing_critical: bool | None = None
    schema_version: str | None = None


class HealthPoint(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: UtcDatetime
    health_index: FiniteFloat | None = Field(default=None, ge=0, le=100)
    health_components: HealthComponents | None = None
    health_reason_codes: list[ReasonCode] | None = None
    inference_status: Literal["OK", "INSUFFICIENT_DATA"]


class AnalyticsPoint(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: UtcDatetime
    anomaly_score: FiniteFloat | None = Field(default=None, ge=0, le=1)
    anomaly_flag: bool | None = None
    fault_risk: FiniteFloat | None = Field(default=None, ge=0, le=1)
    predicted_fault: str | None = None
    prediction_confidence: FiniteFloat | None = Field(default=None, ge=0, le=1)
    thermal_model_temperature: FiniteFloat | None = None
    thermal_residual: FiniteFloat | None = None
    thermal_state: str | None = None
    loading_percent: FiniteFloat | None = None
    maintenance_priority: MaintenancePriority | None = None
    reason_codes: list[ReasonCode] | None = None
    inference_status: Literal["OK", "INSUFFICIENT_DATA"]
    schema_version: str
    feature_version: str
    model_version: str


class DataSource(CanonicalModel):
    source_name: str | None = None
    scenario_id: str | None = None


class TrendBucket(CanonicalModel):
    bucket_start: UtcDatetime
    avg: FiniteFloat | None = None
    min: FiniteFloat | None = None
    max: FiniteFloat | None = None
    count: int = Field(ge=0)


class ProtectionEvent(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: UtcDatetime
    oil_temp_alarm: int | None = None
    oil_temp_trip: int | None = None
    magnetic_oil_gauge_alarm: int | None = None


class TrendOut(CanonicalModel):
    start: UtcDatetime
    end: UtcDatetime
    bucket_seconds: int = Field(gt=0)
    signals: dict[str, list[TrendBucket]]
    no_data_signals: list[str]
    protection_events: list[ProtectionEvent]


class ScenarioOut(CanonicalModel):
    scenario_id: str
    first_timestamp: UtcDatetime
    last_timestamp: UtcDatetime
    row_count: int = Field(ge=1)
