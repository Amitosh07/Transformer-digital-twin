"""Data completeness only; zero counts as present and unverified units stay untouched."""

from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS
from app.schemas.telemetry import TelemetryIn

CRITICAL_FIELDS = (
    "oil_temperature",
    "current_l1",
    "current_l2",
    "current_l3",
    "phase_voltage_l1",
    "phase_voltage_l2",
    "phase_voltage_l3",
)


def compute_is_missing_critical(record: TelemetryIn) -> bool:
    return any(getattr(record, field) is None for field in CRITICAL_FIELDS)


def compute_data_quality_score(record: TelemetryIn) -> float:
    fields = [
        field
        for field in CANONICAL_TELEMETRY_FIELDS
        if field not in {"transformer_id", "timestamp"}
    ]
    return sum(getattr(record, field) is not None for field in fields) / len(fields)
