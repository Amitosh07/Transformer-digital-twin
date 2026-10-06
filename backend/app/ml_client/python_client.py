"""Lazy adapter for the public Person-1 callable; pandas is not required."""

from collections.abc import Callable
from importlib import import_module

from app.core.config import Settings, get_settings
from app.ml_client.base import (
    MLClientError,
    MLTimeoutError,
    parse_ml_result,
    validate_history,
    validate_result_identity,
)
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


class PythonMLTwinClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else get_settings()
        self._entrypoint: Callable[..., object] | None = None

    def _load_entrypoint(self) -> Callable[..., object]:
        if self._entrypoint is not None:
            return self._entrypoint
        entrypoint = self.settings.ml_python_entrypoint
        if not entrypoint or entrypoint.count(":") != 1:
            raise MLClientError("Set ML_PYTHON_ENTRYPOINT to module.path:function")
        module_name, function_name = entrypoint.split(":")
        if not module_name or not function_name.isidentifier():
            raise MLClientError("ML_PYTHON_ENTRYPOINT must use module.path:function")
        try:
            function = getattr(import_module(module_name), function_name)
        except Exception as exc:
            raise MLClientError("Unable to import the configured ML Python entrypoint") from exc
        if not callable(function):
            raise MLClientError("Configured ML Python entrypoint is not callable")
        self._entrypoint = function
        return function

    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        validate_history(transformer, record, history, self.settings.ml_history_window)
        function = self._load_entrypoint()
        try:
            value = function(
                transformer=transformer.model_dump(mode="python"),
                record=record.model_dump(mode="python"),
                history=[row.model_dump(mode="python") for row in history],
            )
        except (TimeoutError, MLTimeoutError) as exc:
            raise MLTimeoutError("ML Python analysis timed out") from exc
        except Exception as exc:
            raise MLClientError("ML Python entrypoint failed") from exc
        return validate_result_identity(parse_ml_result(value), record)
