import logging
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services import query_service


def test_request_id_metadata_and_no_body_logging(
    hard_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    body = {"transformer_id": "secret-body-marker", "timestamp": "naive", "oil_temperature": 98765}
    with caplog.at_level(logging.INFO, logger="app.core.request_logging"):
        response = hard_client.post(
            "/api/v1/telemetry", json=body, headers={"X-Request-ID": "phase8-request-1"}
        )
    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "phase8-request-1"
    assert response.json()["error"]["details"][-1] == {"request_id": "phase8-request-1"}
    rows = [row for row in caplog.records if row.name == "app.core.request_logging"]
    assert len(rows) == 1
    row = rows[0]
    assert row.request_id == "phase8-request-1" and row.method == "POST"
    assert row.path == "/api/v1/telemetry" and row.status == 422 and row.duration_ms >= 0
    assert "secret-body-marker" not in row.getMessage() and "98765" not in row.getMessage()


@pytest.mark.parametrize("value", [None, "bad id with spaces", "x" * 129])
def test_generated_safe_request_ids(hard_client: TestClient, value: str | None) -> None:
    response = hard_client.get("/health", headers={"X-Request-ID": value} if value else {})
    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])


@pytest.mark.parametrize(
    "exception",
    [RuntimeError("private-service-secret"), HTTPException(500, "private-service-secret")],
)
def test_service_exceptions_never_reach_clients(
    hard_client: TestClient, monkeypatch: pytest.MonkeyPatch, exception: Exception
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise exception

    monkeypatch.setattr(query_service, "latest", fail)
    response = hard_client.get(
        "/api/v1/transformers/TX-broken/latest", headers={"X-Request-ID": "error-request"}
    )
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "error-request"
    assert response.json()["error"]["details"] == {"request_id": "error-request"}
    assert "private-service-secret" not in response.text
    assert "traceback" not in response.text.casefold()


def test_404_correlation_and_cors_header(hard_client: TestClient) -> None:
    response = hard_client.get(
        "/missing", headers={"Origin": "http://localhost:8501", "X-Request-ID": "missing-request"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["details"]["request_id"] == "missing-request"
    assert response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"
    preflight = hard_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["X-Request-ID"]
