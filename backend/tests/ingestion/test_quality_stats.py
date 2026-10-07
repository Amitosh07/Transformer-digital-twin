from typing import Any

import pytest

from app.schemas.ingestion import ReplayIn
from app.services.quality_stats import parse_records

from .conftest import make_record


def test_stats_use_unique_times_per_asset_and_count_missing_over_valid_rows() -> None:
    rows = [make_record("TX-one", value) for value in [5, 0, 0]]
    rows += [make_record("TX-two", value) for value in [0, 10]]
    records, stats = parse_records(rows, "test")
    assert len(records) == 5
    assert stats.missing_count_by_field["neutral_current"] == 5
    assert stats.missing_count_by_field["current_l1"] == 0
    assert stats.gap_stats() == {"min_s": 5, "median_s": 7.5, "max_s": 10, "count": 2}
    _, empty = parse_records([], "test")
    assert empty.gap_stats() == {"min_s": None, "median_s": None, "max_s": None, "count": 0}


@pytest.mark.parametrize(
    "field,value,range_count",
    [
        ("power_factor_l1", 1.5, 1),
        ("oil_temp_alarm", 2, 1),
        ("power_factor_l1", float("nan"), 0),
        ("current_l1", float("inf"), 0),
        ("oil_temp_alarm", float("nan"), 0),
    ],
)
def test_error_classification(field: str, value: object, range_count: int) -> None:
    _, stats = parse_records([make_record("TX-one", 0) | {field: value}], "test")
    assert stats.out_of_range_count == range_count
    assert stats.parse_error_count == 1 - range_count


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "records": [],
            "from_stored": {"start": "2026-10-06T00:00:00Z", "end": "2026-10-07T00:00:00Z"},
        },
        {"records": [], "speed_multiplier": -1},
        {"from_stored": {"start": "2026-10-07T00:00:00Z", "end": "2026-10-06T00:00:00Z"}},
    ],
)
def test_replay_source_and_speed_constraints(payload: dict[str, Any]) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReplayIn.model_validate(payload)
