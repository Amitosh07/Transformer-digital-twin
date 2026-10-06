from datetime import UTC

import pytest
from pydantic import ValidationError

from app.schemas.health import HealthResponse
from app.schemas.telemetry import TelemetryInput

BASE = {"transformer_id": "TX-001", "timestamp": "2026-10-06T11:30:00+05:30"}


def test_missing_values_and_utc() -> None:
    record = TelemetryInput(**BASE)
    assert record.oil_temperature is None
    assert record.current_l1 is None
    assert record.timestamp.tzinfo == UTC
    assert record.timestamp.hour == 6
    assert record.timestamp.minute == 0


@pytest.mark.parametrize("value", [0, 1, True, False, None])
def test_protection_values(value: object) -> None:
    record = TelemetryInput(**BASE, oil_temp_alarm=value)
    assert record.oil_temp_alarm == value


@pytest.mark.parametrize("value", [2, -1, "1", "true", 1.0, []])
def test_invalid_protection(value: object) -> None:
    with pytest.raises(ValidationError):
        TelemetryInput(**BASE, oil_temp_alarm=value)


@pytest.mark.parametrize("field", ["vl12", "vl23", "vl31", "VL12", "VL23", "VL31", "unknown"])
def test_extra_fields_forbidden(field: str) -> None:
    with pytest.raises(ValidationError):
        TelemetryInput(**BASE, **{field: 1})


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        TelemetryInput(transformer_id="TX-001", timestamp="2026-10-06T11:30:00")


@pytest.mark.parametrize(
    "field",
    [
        "oil_temperature",
        "winding_temperature",
        "ambient_temperature",
        "oil_level",
    ],
)
def test_unverified_fields_have_no_range_checks(field: str) -> None:
    assert getattr(TelemetryInput(**BASE, **{field: -9999}), field) == -9999
    with pytest.raises(ValidationError):
        TelemetryInput(**BASE, **{field: "status"})


def test_health_schema_forbids_extras() -> None:
    with pytest.raises(ValidationError):
        HealthResponse(status="ok", db="ok", schema_version="1.0.0", secret="hidden")


@pytest.mark.parametrize("value", [1728129600, True, None])
def test_timestamp_requires_datetime_input(value: object) -> None:
    with pytest.raises(ValidationError):
        TelemetryInput(transformer_id="TX-001", timestamp=value)
