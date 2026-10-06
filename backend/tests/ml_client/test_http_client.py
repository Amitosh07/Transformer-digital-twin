import json

import httpx
import pytest

from app.core.config import Settings
from app.ml_client.base import MLClientError, MLTimeoutError
from app.ml_client.http_client import HttpMLTwinClient
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, ml_http_url="https://twin.example/analyze", **values)


def test_http_success_uses_json_dates_and_preserves_history(
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
    valid_result: MLResultIn,
) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/analyze"
        payload = json.loads(request.content)
        assert payload == {
            "transformer": transformer.model_dump(mode="json"),
            "record": record.model_dump(mode="json"),
            "history": [row.model_dump(mode="json") for row in history],
        }
        assert payload["record"]["timestamp"].endswith("Z")
        assert payload["record"]["current_l1"] is None
        assert request.extensions["timeout"]["read"] == 5
        return httpx.Response(200, json=valid_result.model_dump(mode="json"))

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        client = HttpMLTwinClient(settings(), http_client=http_client)
        assert client.analyze(transformer, record, history) == valid_result
        client.close()
        assert not http_client.is_closed


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectTimeout])
def test_timeout_is_not_retried(
    exception: type[httpx.TimeoutException],
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise exception("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        with pytest.raises(MLTimeoutError):
            HttpMLTwinClient(settings(), http_client=http_client).analyze(transformer, record, [])
    assert calls == 1


@pytest.mark.parametrize("first_failure", ["server", "connection"])
def test_retry_then_success(
    first_failure: str,
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
) -> None:
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 2:
            if first_failure == "connection":
                raise httpx.ConnectError("connection failed", request=request)
            return httpx.Response(503)
        return httpx.Response(200, json=valid_result.model_dump(mode="json"))

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        assert (
            HttpMLTwinClient(settings(), http_client=http_client).analyze(
                transformer,
                record,
                [],
            )
            == valid_result
        )
    assert calls == 3


@pytest.mark.parametrize(
    "status,expected_calls", [(500, 3), (503, 3), (400, 1), (429, 1), (302, 1)]
)
def test_retry_budget_and_non_retryable_statuses(
    status: int,
    expected_calls: int,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        with pytest.raises(MLClientError, match=f"status {status}"):
            HttpMLTwinClient(settings(), http_client=http_client).analyze(transformer, record, [])
    assert calls == expected_calls


@pytest.mark.parametrize("mode", ["malformed", "missing", "invalid", "array"])
def test_invalid_responses_are_not_retried(
    mode: str,
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
) -> None:
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if mode == "malformed":
            return httpx.Response(200, text="{invalid")
        payload = valid_result.model_dump(mode="json")
        if mode == "missing":
            del payload["schema_version"]
        elif mode == "invalid":
            payload["fault_risk"] = 1.5
        return httpx.Response(200, json=[] if mode == "array" else payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        with pytest.raises(MLClientError):
            HttpMLTwinClient(settings(), http_client=http_client).analyze(transformer, record, [])
    assert calls == 1


def test_extra_response_keys_are_dropped_with_warning(
    transformer: TransformerOut,
    record: TelemetryIn,
    valid_result: MLResultIn,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = valid_result.model_dump(mode="json") | {"extra_prediction_metadata": "unused"}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with httpx.Client(transport=transport) as http_client:
        result = HttpMLTwinClient(settings(), http_client=http_client).analyze(
            transformer, record, []
        )
    assert result == valid_result
    assert "extra_prediction_metadata" in caplog.text


@pytest.mark.parametrize("url", [None, "file:///local", "https://", "not-a-url"])
def test_http_requires_service_url(url: str | None) -> None:
    with pytest.raises(MLClientError, match="ML_HTTP_URL"):
        HttpMLTwinClient(Settings(_env_file=None, ml_http_url=url))


def test_owned_client_closes() -> None:
    client = HttpMLTwinClient(settings())
    client.close()
    assert client._client.is_closed


@pytest.mark.parametrize("retries,timeout", [(0, 0.25), (1, 1.25)])
def test_custom_timeout_and_connection_retry_exhaustion(
    retries: int,
    timeout: float,
    transformer: TransformerOut,
    record: TelemetryIn,
) -> None:
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.extensions["timeout"]["read"] == timeout
        raise httpx.ConnectError("failed connection", request=request)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        client = HttpMLTwinClient(
            settings(ml_max_retries=retries, ml_timeout_seconds=timeout), http_client=http_client
        )
        with pytest.raises(MLClientError, match="connect"):
            client.analyze(transformer, record, [])
    assert calls == retries + 1
