import sys
from datetime import datetime
from types import ModuleType
from typing import Any

import pytest

from app.core.config import Settings
from app.ml_client.base import MLClientError, MLTimeoutError
from app.ml_client.python_client import PythonMLTwinClient
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


def test_lazy_fake_entrypoint_and_plain_dicts(
    monkeypatch: pytest.MonkeyPatch,
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
    valid_result: MLResultIn,
) -> None:
    import app.ml_client.python_client as module

    fake = ModuleType("test_twin_package")
    calls: list[dict[str, Any]] = []

    def analyze(**payload: Any) -> dict[str, Any]:
        calls.append(payload)
        return valid_result.model_dump()

    fake.analyze = analyze
    imports: list[str] = []

    def importer(name: str) -> ModuleType:
        imports.append(name)
        return fake

    monkeypatch.setattr(module, "import_module", importer)
    settings = Settings(_env_file=None, ml_python_entrypoint="test_twin_package:analyze")
    client = PythonMLTwinClient(settings)
    assert imports == []
    assert client.analyze(transformer, record, history) == valid_result
    assert client.analyze(transformer, record, history) == valid_result
    assert imports == ["test_twin_package"]
    payload = calls[0]
    assert isinstance(payload["record"], dict)
    assert isinstance(payload["record"]["timestamp"], datetime)
    assert payload["record"]["current_l1"] is None
    assert payload["history"] == [row.model_dump() for row in history]
    assert payload["transformer"] == transformer.model_dump()


@pytest.mark.parametrize(
    "entrypoint",
    [None, "", "missing-module", ":analyze", "test_twin_package:", "test_twin_package:missing"],
)
def test_missing_entrypoint_is_client_error(
    entrypoint: str | None,
    monkeypatch: pytest.MonkeyPatch,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    monkeypatch.setitem(sys.modules, "test_twin_package", ModuleType("test_twin_package"))
    client = PythonMLTwinClient(Settings(_env_file=None, ml_python_entrypoint=entrypoint))
    with pytest.raises(MLClientError):
        client.analyze(transformer, record, [])


def test_uninstalled_ml_package_does_not_break_construction(
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    client = PythonMLTwinClient(
        Settings(_env_file=None, ml_python_entrypoint="absent_twin_package:analyze")
    )
    with pytest.raises(MLClientError, match="import"):
        client.analyze(transformer, record, [])


@pytest.mark.parametrize("mode", ["extra", "missing", "not_callable", "raises", "timeout"])
def test_python_response_and_entrypoint_errors(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
) -> None:
    fake = ModuleType("test_twin_package")

    def analyze(**payload: Any) -> dict[str, Any]:
        if mode == "raises":
            raise RuntimeError("private ML internals")
        if mode == "timeout":
            raise TimeoutError("private timeout")
        result = valid_result.model_dump()
        if mode == "extra":
            result["extra_prediction_metadata"] = "unused"
        if mode == "missing":
            del result["feature_version"]
        return result

    fake.analyze = 3 if mode == "not_callable" else analyze
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    client = PythonMLTwinClient(
        Settings(_env_file=None, ml_python_entrypoint="test_twin_package:analyze")
    )
    if mode == "extra":
        assert client.analyze(transformer, record, []) == valid_result
        assert "extra_prediction_metadata" in caplog.text
    else:
        with pytest.raises(MLTimeoutError if mode == "timeout" else MLClientError):
            client.analyze(transformer, record, [])
