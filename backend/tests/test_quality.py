import pytest

from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS
from app.schemas.quality import (
    CRITICAL_FIELDS,
    compute_data_quality_score,
    compute_is_missing_critical,
)
from app.schemas.telemetry import TelemetryIn

BASE = {"transformer_id": "TX-001", "timestamp": "2026-10-06T00:00:00Z"}


def test_minimal_record_quality() -> None:
    record = TelemetryIn(**BASE)
    assert compute_is_missing_critical(record) is True
    assert compute_data_quality_score(record) == 0


def test_quality_counts_zero_but_excludes_metadata() -> None:
    record = TelemetryIn(
        **BASE,
        current_l1=0,
        oil_temp_alarm=False,
        source_name="simulator",
        scenario_id="scenario-1",
    )
    assert compute_data_quality_score(record) == pytest.approx(2 / 21)


@pytest.mark.parametrize("missing", CRITICAL_FIELDS)
def test_each_critical_measurement_is_required_for_completeness(missing: str) -> None:
    values = dict.fromkeys(CRITICAL_FIELDS, 0)
    assert compute_is_missing_critical(TelemetryIn(**BASE, **values)) is False
    values[missing] = None
    assert compute_is_missing_critical(TelemetryIn(**BASE, **values)) is True


def test_complete_record_and_missing_oil_temperature() -> None:
    values = dict.fromkeys(CANONICAL_TELEMETRY_FIELDS[2:], 0)
    complete = TelemetryIn(**BASE, **values)
    assert compute_data_quality_score(complete) == 1
    assert compute_is_missing_critical(complete) is False
    values["oil_temperature"] = None
    missing_oil = TelemetryIn(**BASE, **values)
    assert compute_is_missing_critical(missing_oil) is True
    assert compute_data_quality_score(missing_oil) == pytest.approx(20 / 21)
