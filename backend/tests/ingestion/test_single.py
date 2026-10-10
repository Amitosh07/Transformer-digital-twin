from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ml_client.stub_client import StubMLTwinClient
from app.models import Analytics, Telemetry, Transformer
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(
        self, transformer: TransformerOut, record: TelemetryIn, history: list[TelemetryIn]
    ) -> MLResultIn:
        self.calls += 1
        return StubMLTwinClient().analyze(transformer, record, history)


def test_single_and_duplicate_are_persisted_and_idempotent(
    ingest_client: TestClient,
    payload: dict[str, Any],
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.ingestion_service as service

    client = CountingClient()
    monkeypatch.setattr(service, "get_ml_client", lambda: client)
    payload["scenario_id"] = "test-scenario"
    first = ingest_client.post("/api/v1/telemetry", json=payload)
    assert first.status_code == 201
    data = first.json()
    assert data["analytics"]["model_version"] == "stub-0.0.0"
    assert data["analytics"]["schema_version"] == "1.0.0"
    assert data["analytics"]["feature_version"] == "1.0.0"
    second = ingest_client.post("/api/v1/telemetry", json=payload)
    assert second.status_code == 200
    assert second.json() == {"duplicate": True, "telemetry_id": data["telemetry_id"]}
    assert client.calls == 1
    row = ingestion_session.get(Telemetry, data["telemetry_id"])
    assert row.source_name == "api"
    assert row.scenario_id == "test-scenario"
    assert row.current_l1 == 0
    assert (
        ingestion_session.scalar(
            select(func.count())
            .select_from(Telemetry)
            .where(
                Telemetry.transformer_id == payload["transformer_id"],
            )
        )
        == 1
    )
    assert (
        ingestion_session.scalar(
            select(func.count())
            .select_from(Analytics)
            .where(
                Analytics.telemetry_id == row.id,
            )
        )
        == 1
    )
    transformer = ingestion_session.get(Transformer, payload["transformer_id"])
    assert transformer.name == transformer.id
    for field in [
        "rated_power_kva",
        "rated_voltage_hv",
        "rated_voltage_lv",
        "rated_current_a",
        "cooling_class",
        "oil_type",
    ]:
        assert getattr(transformer, field) is None


def test_missing_values_stay_null(
    ingest_client: TestClient,
    payload: dict[str, Any],
    ingestion_session: Session,
) -> None:
    payload["oil_temperature"] = None
    response = ingest_client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert "MISSING_CRITICAL" in result["warnings"]
    assert "INSUFFICIENT_DATA" in result["warnings"]
    assert result["analytics"]["missing_features"] == ["oil_temperature"]
    row = ingestion_session.get(Telemetry, result["telemetry_id"])
    assert row.oil_temperature is None
    assert row.is_missing_critical is True
    assert row.data_quality_score == pytest.approx(8 / 21)
    assert (
        ingestion_session.scalar(
            text("SELECT oil_temperature IS NULL FROM telemetry WHERE id=:id"), {"id": row.id}
        )
        is True
    )


@pytest.mark.parametrize("exception", [RuntimeError, httpx.ReadTimeout])
def test_ml_failure_does_not_lose_telemetry(
    exception: type[Exception],
    ingest_client: TestClient,
    payload: dict[str, Any],
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.ingestion_service as service

    class FailingClient:
        def analyze(
            self, transformer: TransformerOut, record: TelemetryIn, history: list[TelemetryIn]
        ) -> MLResultIn:
            raise exception("private details")

    monkeypatch.setattr(service, "get_ml_client", FailingClient)
    response = ingest_client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert "ML_UNAVAILABLE" in result["warnings"]
    assert result["analytics"]["inference_status"] == "INSUFFICIENT_DATA"
    assert (
        result["analytics"]["feature_version"]
        == result["analytics"]["model_version"]
        == "unavailable"
    )
    assert result["analytics"]["error_detail"]
    assert ingestion_session.get(Telemetry, result["telemetry_id"]) is not None
    assert ingestion_session.scalar(
        select(Analytics).where(
            Analytics.telemetry_id == result["telemetry_id"],
        )
    ).error_detail


def test_client_factory_failure_is_also_isolated(
    ingest_client: TestClient,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.ingestion_service as service

    def fail() -> None:
        raise ValueError("missing service configuration")

    monkeypatch.setattr(service, "get_ml_client", fail)
    response = ingest_client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 201
    assert "ML_UNAVAILABLE" in response.json()["warnings"]


@pytest.mark.parametrize("failure", ["python", "database"])
def test_alert_hook_failure_cannot_rollback_saved_rows(
    failure: str,
    ingest_client: TestClient,
    payload: dict[str, Any],
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.hooks as hooks

    def broken(session: Session, telemetry: Telemetry, analytics: Analytics) -> None:
        if failure == "database":
            session.execute(text("SELECT 1 / 0"))
        raise RuntimeError("hook failure")

    monkeypatch.setattr(hooks, "evaluate_alerts", broken)
    response = ingest_client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert "ALERT_HOOK_FAILED" in result["warnings"]
    assert ingestion_session.get(Telemetry, result["telemetry_id"]) is not None
    assert (
        ingestion_session.scalar(
            select(Analytics).where(
                Analytics.telemetry_id == result["telemetry_id"],
            )
        )
        is not None
    )


def test_run_ml_false_stores_only_telemetry(
    ingest_client: TestClient,
    payload: dict[str, Any],
    ingestion_session: Session,
) -> None:
    response = ingest_client.post("/api/v1/telemetry?run_ml=false", json=payload)
    assert response.status_code == 201
    assert response.json()["analytics"] is None
    assert (
        ingestion_session.scalar(
            select(Analytics).where(
                Analytics.telemetry_id == response.json()["telemetry_id"],
            )
        )
        is None
    )
