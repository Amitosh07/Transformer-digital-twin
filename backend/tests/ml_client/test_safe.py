from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.ml_client.base import MLClientError, MLTimeoutError
from app.ml_client.safe import safe_analyze
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


class FakeClient:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    "exception", [RuntimeError, MLClientError, MLTimeoutError, TimeoutError, httpx.ReadTimeout]
)
def test_failures_never_escape(
    exception: type[Exception],
    transformer: TransformerOut,
    record: TelemetryIn,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ml_client.safe as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(_env_file=None, schema_version="2.0.0")
    )
    result = safe_analyze(
        FakeClient(error=exception("private traceback details")), transformer, record, []
    )
    assert result.inference_status == "INSUFFICIENT_DATA"
    assert result.schema_version == "2.0.0"
    assert result.feature_version == result.model_version == "unavailable"
    assert result.error_detail
    assert "private" not in result.error_detail
    assert "traceback" not in result.error_detail
    outputs = {
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
    }
    assert all(getattr(result, field) is None for field in outputs)
    assert result.transformer_id == record.transformer_id
    assert result.timestamp == record.timestamp
    assert "TX-001" in caplog.text
    assert record.timestamp.isoformat() in caplog.text
    assert MLResultIn.model_validate(result.model_dump()) == result


@pytest.mark.parametrize("mode", ["dict", "mutated_model", "none", "wrong_identity", "validation"])
def test_invalid_results_are_isolated(
    mode: str,
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
) -> None:
    value: Any = valid_result
    error = None
    if mode == "dict":
        value = valid_result.model_dump() | {"health_index": 120}
    elif mode == "mutated_model":
        valid_result.fault_risk = 1.5
    elif mode == "none":
        value = None
    elif mode == "wrong_identity":
        value = valid_result.model_copy(update={"transformer_id": "TX-OTHER"})
    else:
        try:
            MLResultIn.model_validate({})
        except ValidationError as exc:
            error = exc
    result = safe_analyze(FakeClient(result=value, error=error), transformer, record, [])
    assert result.inference_status == "INSUFFICIENT_DATA"
    assert result.error_detail
    assert result.feature_version == result.model_version == "unavailable"


def test_valid_result_passes_through(
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
) -> None:
    assert safe_analyze(FakeClient(result=valid_result), transformer, record, []) == valid_result


def test_configuration_failure_still_returns_valid_fallback(
    monkeypatch: pytest.MonkeyPatch,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    import app.ml_client.safe as module

    def failed_settings() -> Settings:
        raise ValueError("invalid configuration")

    monkeypatch.setattr(module, "get_settings", failed_settings)
    result = safe_analyze(FakeClient(error=RuntimeError("failed")), transformer, record, [])
    assert result.inference_status == "INSUFFICIENT_DATA"
    assert result.schema_version == "1.0.0"
