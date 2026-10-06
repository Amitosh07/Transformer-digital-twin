from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.models import Telemetry
from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS
from app.schemas.telemetry import TelemetryBatchIn, TelemetryIn, TelemetryOut

BASE = {"transformer_id": "TX-001", "timestamp": "2026-10-06T11:30:00+05:30"}
PROTECTION = ["oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm"]
MEASUREMENTS = [name for name in CANONICAL_TELEMETRY_FIELDS[2:] if name not in PROTECTION]


def test_canonical_fields_match_schema_and_orm() -> None:
    expected = [
        "transformer_id",
        "timestamp",
        "phase_voltage_l1",
        "phase_voltage_l2",
        "phase_voltage_l3",
        "current_l1",
        "current_l2",
        "current_l3",
        "neutral_current",
        "oil_temperature",
        "winding_temperature",
        "ambient_temperature",
        "oil_level",
        "oil_temp_alarm",
        "oil_temp_trip",
        "magnetic_oil_gauge_alarm",
        "active_power_total",
        "apparent_power_total",
        "reactive_power_total",
        "energy_kwh",
        "power_factor_l1",
        "power_factor_l2",
        "power_factor_l3",
    ]
    assert CANONICAL_TELEMETRY_FIELDS == expected
    assert list(TelemetryIn.model_fields) == expected + ["source_name", "scenario_id"]
    metadata = {
        "id",
        "source_name",
        "scenario_id",
        "is_duplicate",
        "is_missing_critical",
        "data_quality_score",
        "schema_version",
        "ingested_at",
    }
    orm_fields = set(Telemetry.__table__.columns.keys()) - metadata
    assert set(CANONICAL_TELEMETRY_FIELDS) == orm_fields
    assert len(CANONICAL_TELEMETRY_FIELDS) == len(orm_fields)


def test_minimal_payload_keeps_all_optionals_missing() -> None:
    record = TelemetryIn(**BASE)
    assert record.timestamp == datetime(2026, 10, 6, 6, 0, tzinfo=UTC)
    for field in CANONICAL_TELEMETRY_FIELDS[2:] + ["source_name", "scenario_id"]:
        assert getattr(record, field) is None
    assert record.model_dump(mode="json")["timestamp"] == "2026-10-06T06:00:00Z"


@pytest.mark.parametrize(
    "field", ["VL12", "vl23", "VL31", "VL_12", "vl_23", "Vl_31", "v_l_1_2", "VL-23", "VL 31"]
)
def test_excluded_variants_have_clear_message(field: str) -> None:
    with pytest.raises(ValidationError, match="excluded from the canonical schema") as error:
        TelemetryIn(**BASE, **{field: 99})
    assert field in str(error.value)


@pytest.mark.parametrize("field", PROTECTION)
@pytest.mark.parametrize("value,expected", [(0, 0), (1, 1), (False, 0), (True, 1), (None, None)])
def test_protection_normalizes_only_binary_values(
    field: str, value: object, expected: int | None
) -> None:
    result = TelemetryIn(**BASE, **{field: value})
    assert getattr(result, field) == expected
    if expected is not None:
        assert type(getattr(result, field)) is int


@pytest.mark.parametrize("field", PROTECTION)
@pytest.mark.parametrize("value", [2, -1, 0.0, 1.0, "1", "false"])
def test_protection_rejects_other_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TelemetryIn(**BASE, **{field: value})


@pytest.mark.parametrize("field", MEASUREMENTS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_all_measurement_floats_must_be_finite(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        TelemetryIn(**BASE, **{field: value})


@pytest.mark.parametrize("field", ["power_factor_l1", "power_factor_l2", "power_factor_l3"])
@pytest.mark.parametrize("value", [-1.5, 1.5])
def test_power_factor_range(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        TelemetryIn(**BASE, **{field: value})


@pytest.mark.parametrize("field", ["power_factor_l1", "power_factor_l2", "power_factor_l3"])
@pytest.mark.parametrize("value", [-1, 0, 1, None])
def test_power_factor_boundaries(field: str, value: float | None) -> None:
    assert getattr(TelemetryIn(**BASE, **{field: value}), field) == value


def test_optional_metadata_stays_out_of_canonical_fields() -> None:
    record = TelemetryIn(**BASE, source_name="simulator", scenario_id="scenario-1")
    assert record.source_name == "simulator"
    assert record.scenario_id == "scenario-1"
    assert "source_name" not in CANONICAL_TELEMETRY_FIELDS
    assert "scenario_id" not in CANONICAL_TELEMETRY_FIELDS


def test_telemetry_out_validates_floats_too() -> None:
    with pytest.raises(ValidationError):
        TelemetryOut(
            **BASE,
            id=1,
            is_missing_critical=True,
            schema_version="1.0.0",
            data_quality_score=float("nan"),
        )


def test_batch_limit_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_BATCH_SIZE", "2")
    get_settings.cache_clear()
    try:
        assert len(TelemetryBatchIn(records=[BASE, BASE]).records) == 2
        with pytest.raises(ValidationError, match="MAX_BATCH_SIZE.*2"):
            TelemetryBatchIn(records=[BASE, BASE, BASE])
        assert TelemetryBatchIn(records=[]).records == []
        with pytest.raises(ValidationError):
            TelemetryBatchIn(records=iter([BASE]))
    finally:
        get_settings.cache_clear()


def test_default_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAX_BATCH_SIZE", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().max_batch_size == 5000
        assert len(TelemetryBatchIn(records=[BASE] * 5000).records) == 5000
        with pytest.raises(ValidationError, match="MAX_BATCH_SIZE.*5000"):
            TelemetryBatchIn(records=[BASE] * 5001)
    finally:
        get_settings.cache_clear()
