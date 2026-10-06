import pytest

from app.core.config import Settings
from app.ml_client.base import MLClientError
from app.ml_client.stub_client import StubMLTwinClient
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


def test_insufficient_precedes_trip(transformer: TransformerOut, record: TelemetryIn) -> None:
    result = StubMLTwinClient().analyze(
        transformer,
        record.model_copy(update={"oil_temperature": None, "oil_level": None, "oil_temp_trip": 1}),
        [],
    )
    assert result.inference_status == "INSUFFICIENT_DATA"
    assert result.missing_features == ["oil_temperature", "oil_level"]
    metadata = {
        "transformer_id",
        "timestamp",
        "inference_status",
        "missing_features",
        "schema_version",
        "feature_version",
        "model_version",
        "error_detail",
    }
    assert all(getattr(result, field) is None for field in set(MLResultIn.model_fields) - metadata)


@pytest.mark.parametrize("missing", ["oil_temperature", "oil_level"])
def test_individual_missing_features(
    missing: str,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    result = StubMLTwinClient().analyze(transformer, record.model_copy(update={missing: None}), [])
    assert result.missing_features == [missing]


def test_trip_rule(transformer: TransformerOut, record: TelemetryIn) -> None:
    result = StubMLTwinClient().analyze(
        transformer,
        record.model_copy(
            update={
                "oil_temp_trip": 1,
                "oil_temp_alarm": 1,
                "magnetic_oil_gauge_alarm": 1,
            }
        ),
        [],
    )
    assert result.maintenance_priority == "URGENT"
    assert result.reason_codes == ["OIL_TEMP_TRIP"]
    assert (result.anomaly_flag, result.anomaly_score, result.health_index, result.fault_risk) == (
        True,
        0.95,
        25,
        0.9,
    )
    assert result.predicted_fault == "THERMAL_STRESS"


def test_alarm_rule(transformer: TransformerOut, record: TelemetryIn) -> None:
    result = StubMLTwinClient().analyze(
        transformer,
        record.model_copy(
            update={
                "oil_temp_alarm": 1,
                "magnetic_oil_gauge_alarm": 1,
            }
        ),
        [],
    )
    assert result.maintenance_priority == "PLAN"
    assert result.reason_codes == ["OIL_TEMP_ALARM", "HIGH_OIL_TEMP"]
    assert (result.anomaly_flag, result.anomaly_score, result.health_index, result.fault_risk) == (
        True,
        0.75,
        55,
        0.6,
    )
    assert result.predicted_fault == "THERMAL_STRESS"


def test_mog_rule(transformer: TransformerOut, record: TelemetryIn) -> None:
    result = StubMLTwinClient().analyze(
        transformer,
        record.model_copy(update={"magnetic_oil_gauge_alarm": 1}),
        [],
    )
    assert result.maintenance_priority == "PLAN"
    assert result.reason_codes == ["MOG_ALARM"]
    assert result.health_index == 60
    assert result.predicted_fault is None


def test_normal_rule(transformer: TransformerOut, record: TelemetryIn) -> None:
    result = StubMLTwinClient().analyze(transformer, record, [])
    assert result.inference_status == "OK"
    assert result.maintenance_priority == "NORMAL"
    assert (result.health_index, result.anomaly_score, result.anomaly_flag, result.fault_risk) == (
        90,
        0.1,
        False,
        0.05,
    )
    assert result.reason_codes == []
    assert result.predicted_fault is None


@pytest.mark.parametrize(
    "rating,power,expected", [(None, 50, None), (100, None, None), (100, 50, 50), (100, 0, 0)]
)
def test_loading_cases(
    rating: float | None,
    power: float | None,
    expected: float | None,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    result = StubMLTwinClient().analyze(
        transformer.model_copy(update={"rated_power_kva": rating}),
        record.model_copy(update={"apparent_power_total": power}),
        [],
    )
    assert result.loading_percent == expected


@pytest.mark.parametrize("rating", [0, -1])
def test_invalid_loading_denominator(
    rating: float,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    with pytest.raises(MLClientError, match="positive"):
        StubMLTwinClient().analyze(
            transformer.model_copy(update={"rated_power_kva": rating}),
            record.model_copy(update={"apparent_power_total": 50}),
            [],
        )


@pytest.mark.parametrize(
    "flags",
    [
        {},
        {"oil_temp_trip": 1},
        {"oil_temp_alarm": 1},
        {"magnetic_oil_gauge_alarm": 1},
        {"oil_temperature": None},
    ],
)
def test_each_output_is_deterministic_and_valid(
    flags: dict[str, int | None],
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
    ml_settings: Settings,
) -> None:
    ml_settings.schema_version = "1.2.3"
    client = StubMLTwinClient(ml_settings)
    record = record.model_copy(update=flags)
    first = client.analyze(transformer, record, history)
    second = client.analyze(transformer, record, history)
    assert first == second
    assert MLResultIn.model_validate(first.model_dump()) == first
    assert (first.schema_version, first.feature_version, first.model_version) == (
        "1.2.3",
        "1.0.0",
        "stub-0.0.0",
    )
    if first.inference_status == "OK":
        assert first.maintenance_recommendation
        assert first.health_components is not None
        for score in [first.anomaly_score, first.fault_risk, first.prediction_confidence]:
            assert score is None or 0 <= score <= 1
        assert 0 <= first.health_index <= 100
        assert first.predicted_fault == ("THERMAL_STRESS" if first.fault_risk >= 0.5 else None)


def test_unverified_values_do_not_drive_predictions(
    transformer: TransformerOut, record: TelemetryIn
) -> None:
    client = StubMLTwinClient()
    one = client.analyze(
        transformer,
        record.model_copy(update={"oil_temperature": -100000, "oil_level": -100000}),
        [],
    )
    two = client.analyze(
        transformer, record.model_copy(update={"oil_temperature": 100000, "oil_level": 100000}), []
    )
    assert one == two
    assert one.thermal_model_temperature is None
    assert one.thermal_residual is None
