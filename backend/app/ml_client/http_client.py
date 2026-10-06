"""Synchronous HTTP adapter with bounded retries for connection errors and 5xx only."""

import httpx

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


class HttpMLTwinClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings if settings is not None else get_settings()
        if not self.settings.ml_http_url:
            raise MLClientError("Set ML_HTTP_URL for the http ML backend")
        try:
            url = httpx.URL(self.settings.ml_http_url)
        except httpx.InvalidURL as exc:
            raise MLClientError("ML_HTTP_URL must be an HTTP or HTTPS URL") from exc
        if url.scheme not in {"http", "https"} or not url.host:
            raise MLClientError("ML_HTTP_URL must be an HTTP or HTTPS URL")
        self._url = url
        self._owns_client = http_client is None
        self._client = (
            http_client
            if http_client is not None
            else httpx.Client(
                timeout=self.settings.ml_timeout_seconds,
            )
        )

    def close(self) -> None:
        """Close owned connections; injected clients remain the caller's responsibility."""
        if self._owns_client:
            self._client.close()

    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        validate_history(transformer, record, history, self.settings.ml_history_window)
        payload = {
            "transformer": transformer.model_dump(mode="json"),
            "record": record.model_dump(mode="json"),
            "history": [row.model_dump(mode="json") for row in history],
        }
        for attempt in range(self.settings.ml_max_retries + 1):
            try:
                response = self._client.post(
                    self._url,
                    json=payload,
                    timeout=self.settings.ml_timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                raise MLTimeoutError("ML HTTP analysis timed out") from exc
            except httpx.ConnectError as exc:
                if attempt < self.settings.ml_max_retries:
                    continue
                raise MLClientError("Unable to connect to the ML HTTP service") from exc
            except httpx.HTTPError as exc:
                raise MLClientError("ML HTTP request failed") from exc
            if 500 <= response.status_code <= 599 and attempt < self.settings.ml_max_retries:
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise MLClientError(
                    f"ML HTTP service returned status {response.status_code}"
                ) from exc
            try:
                value = response.json()
            except ValueError as exc:
                raise MLClientError("ML HTTP service returned malformed JSON") from exc
            return validate_result_identity(parse_ml_result(value), record)
        raise MLClientError("ML HTTP retries exhausted")  # Defensive guard.
