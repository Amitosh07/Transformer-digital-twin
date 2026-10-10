import pytest
from pydantic import ValidationError

from app.schemas.analytics import AnalyticsOut, HealthComponents, MLResultIn

BASE = {
    "transformer_id": "TX-001",
    "timestamp": "2026-10-06T00:00:00Z",
    "inference_status": "INSUFFICIENT_DATA",
    "schema_version": "1.0.0",
    "feature_version": "1.0.0",
    "model_version": "stub",
}
FLOAT_FIELDS = [
    "loading_percent",
    "thermal_model_temperature",
    "thermal_residual",
    "anomaly_score",
    "health_index",
    "fault_risk",
    "prediction_confidence",
]


@pytest.mark.parametrize("schema", [MLResultIn, AnalyticsOut])
def test_analytic_shape_and_missing_outputs(schema: type[MLResultIn]) -> None:
    record = schema(**BASE)
    required = {
        "transformer_id",
        "timestamp",
        "inference_status",
        "missing_features",
        "schema_version",
        "feature_version",
        "model_version",
    }
    assert set(schema.model_fields) == required | {
        "loading_percent",
        "thermal_model_temperature",
        "thermal_residual",
        "thermal_state",
        "anomaly_score",
        "anomaly_flag",
        "health_index",
        "health_components",
        "health_reason_codes",
        "fault_risk",
        "predicted_fault",
        "prediction_confidence",
        "maintenance_priority",
        "maintenance_recommendation",
        "reason_codes",
        "error_detail",
        "metadata", "rul",
    }
    for field in set(schema.model_fields) - required:
        assert getattr(record, field) is None
    assert record.missing_features == []
    assert schema(**BASE).missing_features is not record.missing_features


@pytest.mark.parametrize("schema", [MLResultIn, AnalyticsOut])
@pytest.mark.parametrize(
    "field,value",
    [
        ("fault_risk", 1.5),
        ("health_index", 120),
        ("anomaly_score", -0.1),
        ("prediction_confidence", 1.01),
    ],
)
def test_analytic_ranges(schema: type[MLResultIn], field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        schema(**BASE, **{field: value})


@pytest.mark.parametrize("schema", [MLResultIn, AnalyticsOut])
@pytest.mark.parametrize("field", FLOAT_FIELDS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_analytic_float_fields_are_finite(
    schema: type[MLResultIn], field: str, value: float
) -> None:
    with pytest.raises(ValidationError):
        schema(**BASE, **{field: value})


@pytest.mark.parametrize("field", ["thermal", "electrical", "loading", "oil", "alarm", "anomaly"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_health_component_floats_are_finite(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        MLResultIn(**BASE, health_components={field: value})


def test_nested_components_and_enum_values() -> None:
    assert set(HealthComponents.model_fields) == {
        "thermal",
        "electrical",
        "loading",
        "oil",
        "alarm",
        "anomaly",
    }
    record = MLResultIn(
        **BASE,
        health_components={"thermal": 80},
        reason_codes=["OIL_TEMP_ALARM"],
        maintenance_priority="WATCH",
        error_detail="Missing history",
        fault_risk=0,
        health_index=100,
    )
    assert record.health_components.thermal == 80
    assert record.health_components.oil is None
    assert record.error_detail == "Missing history"
    for patch in [
        {"inference_status": "FAILED"},
        {"maintenance_priority": "HIGH"},
        {"reason_codes": ["CONFIRMED_FAULT"]},
        {"health_components": {"unknown": 1}},
    ]:
        with pytest.raises(ValidationError):
            MLResultIn(**(BASE | patch))


def test_analytics_timestamp_rules() -> None:
    with pytest.raises(ValidationError):
        AnalyticsOut(**(BASE | {"timestamp": "2026-10-06T00:00:00"}))
    result = AnalyticsOut(**(BASE | {"timestamp": "2026-10-06T05:30:00+05:30"}))
    assert result.model_dump(mode="json")["timestamp"] == "2026-10-06T00:00:00Z"
