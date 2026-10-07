"""Ingestion envelopes leave record validation to the ingestion service."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.config import get_settings
from app.schemas.analytics import AnalyticsOut
from app.schemas.common import CanonicalModel, FiniteFloat, UtcDatetime


class RawTelemetryBatchIn(CanonicalModel):
    records: list[dict[str, Any]] = Field(strict=True)

    @field_validator("records", mode="before")
    @classmethod
    def enforce_limit(cls, value: object) -> object:
        if isinstance(value, list) and len(value) > get_settings().max_batch_size:
            raise ValueError("Batch exceeds MAX_BATCH_SIZE")
        return value


class StoredWindow(CanonicalModel):
    start: UtcDatetime
    end: UtcDatetime

    @model_validator(mode="after")
    def validate_window(self) -> "StoredWindow":
        if self.start > self.end:
            raise ValueError("start must be at or before end")
        return self


class ReplayIn(CanonicalModel):
    transformer_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_name: str = Field(default="api", min_length=1, max_length=255)
    records: list[dict[str, Any]] | None = Field(default=None, strict=True)
    from_stored: StoredWindow | None = None
    speed_multiplier: FiniteFloat = Field(default=0, ge=0)
    run_ml: bool = True

    @field_validator("records", mode="before")
    @classmethod
    def enforce_limit(cls, value: object) -> object:
        return RawTelemetryBatchIn.enforce_limit(value)

    @model_validator(mode="after")
    def validate_source(self) -> "ReplayIn":
        if (self.records is None) == (self.from_stored is None):
            raise ValueError("Exactly one of records or from_stored must be provided")
        return self


class IngestResult(CanonicalModel):
    telemetry_id: int
    analytics: AnalyticsOut | None = None
    duplicate: bool = False
    warnings: list[str] = Field(default_factory=list)


class ValidationSample(CanonicalModel):
    row_index: int
    field: str
    message: str


class IngestionSummary(CanonicalModel):
    run_id: int
    row_count: int
    inserted_count: int
    duplicate_count: int
    parse_error_count: int
    out_of_range_count: int
    errors_sample: list[ValidationSample]


class ReplayAccepted(CanonicalModel):
    run_id: int


class ReplayStatusOut(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(serialization_alias="run_id")
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    row_count: int
    inserted_count: int
    duplicate_count: int
    parse_error_count: int
    out_of_range_count: int
    missing_count_by_field: dict[str, int] | None
    timestamp_gap_stats: dict[str, Any] | None
    source_name: str
    schema_version: str
    started_at: UtcDatetime
    finished_at: UtcDatetime | None
