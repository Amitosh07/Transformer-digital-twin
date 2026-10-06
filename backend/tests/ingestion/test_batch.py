from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml_client.stub_client import StubMLTwinClient
from app.models import Analytics, IngestionRun, Telemetry
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut
from app.services.ingestion_service import ingest_batch

from .conftest import make_record


def test_partial_batch_validation_and_quality_stats(
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
) -> None:
    rows = [make_record(asset_id, 0), make_record(asset_id, 10)]
    # Rejected source fields are test-only payload keys, never DB/schema columns.
    bad = [
        make_record(asset_id, 20) | {"V" + "L12": 1},
        make_record(asset_id, 21) | {"unknown": "do not echo this"},
        make_record(asset_id, 22) | {"timestamp": "2026-10-06T00:00:22"},
        make_record(asset_id, 23) | {"oil_temperature": float("nan")},
        make_record(asset_id, 24) | {"power_factor_l1": 1.5},
    ]
    # Send raw JSON because httpx intentionally disallows NaN through json=.
    import json

    response = ingest_client.post(
        "/api/v1/telemetry/batch",
        content=json.dumps({"records": rows + bad}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    summary = response.json()
    assert {
        key: summary[key]
        for key in [
            "row_count",
            "inserted_count",
            "duplicate_count",
            "parse_error_count",
            "out_of_range_count",
        ]
    } == {
        "row_count": 7,
        "inserted_count": 2,
        "duplicate_count": 0,
        "parse_error_count": 4,
        "out_of_range_count": 1,
    }
    assert len(summary["errors_sample"]) == 5
    assert "do not echo this" not in response.text
    run = ingestion_session.get(IngestionRun, summary["run_id"])
    assert run.status == "COMPLETED"
    assert run.finished_at is not None
    assert run.missing_count_by_field["neutral_current"] == 2
    assert run.missing_count_by_field["oil_temperature"] == 0
    assert run.timestamp_gap_stats == {"min_s": 10, "median_s": 10, "max_s": 10, "count": 1}


def test_errors_sample_cap_and_max_batch(
    ingest_client: TestClient,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    rows = [make_record(asset_id, second) | {"unknown": 1} for second in range(30)]
    response = ingest_client.post("/api/v1/telemetry/batch", json={"records": rows})
    assert response.status_code == 200
    assert response.json()["parse_error_count"] == 30
    assert len(response.json()["errors_sample"]) == 20
    assert [row["row_index"] for row in response.json()["errors_sample"]] == list(range(20))
    monkeypatch.setenv("MAX_BATCH_SIZE", "1")
    get_settings.cache_clear()
    response = ingest_client.post("/api/v1/telemetry/batch", json={"records": rows})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sorted_history_has_no_per_row_queries_and_includes_interleaved_stored_rows(
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.ingestion_service as service
    from app.repositories import telemetry_repo

    ingest_client.post("/api/v1/telemetry?run_ml=false", json=make_record(asset_id, 2))
    ingest_client.post("/api/v1/telemetry?run_ml=false", json=make_record(asset_id, 4))
    captured: list[tuple[TelemetryIn, list[TelemetryIn]]] = []

    class RecordingClient:
        def analyze(
            self, transformer: TransformerOut, record: TelemetryIn, history: list[TelemetryIn]
        ) -> MLResultIn:
            captured.append((record, history))
            return StubMLTwinClient().analyze(transformer, record, history)

    monkeypatch.setattr(service, "get_ml_client", RecordingClient)
    queries = 0
    original = telemetry_repo.load_batch_history

    def history_once(*args: Any, **kwargs: Any) -> list[TelemetryIn]:
        nonlocal queries
        queries += 1
        return original(*args, **kwargs)

    def unexpected_history(*args: Any, **kwargs: Any) -> list[TelemetryIn]:
        raise AssertionError("Per-row history query")

    monkeypatch.setattr(telemetry_repo, "load_batch_history", history_once)
    monkeypatch.setattr(telemetry_repo, "load_history", unexpected_history)
    response = ingest_client.post(
        "/api/v1/telemetry/batch",
        json={
            "records": [make_record(asset_id, value) for value in [5, 3, 1, 3, 4]],
        },
    )
    assert response.status_code == 200
    assert response.json()["inserted_count"] == 3
    assert response.json()["duplicate_count"] == 2
    assert queries == 1
    assert [record.timestamp.second for record, _ in captured] == [1, 3, 5]
    assert [row.timestamp.second for row in captured[-1][1]] == [1, 2, 3, 4]
    for record, history in captured:
        assert all(row.timestamp < record.timestamp for row in history)
        assert [row.timestamp for row in history] == sorted(row.timestamp for row in history)
        assert len({row.timestamp for row in history}) == len(history)


def test_batch_without_ml_has_no_history_or_analytics(
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import telemetry_repo

    def fail(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("History should not be loaded")

    monkeypatch.setattr(telemetry_repo, "load_batch_history", fail)
    response = ingest_client.post(
        "/api/v1/telemetry/batch?run_ml=false",
        json={
            "records": [make_record(asset_id, value) for value in range(3)],
        },
    )
    assert response.json()["inserted_count"] == 3
    assert (
        ingestion_session.scalar(
            select(func.count())
            .select_from(Analytics)
            .where(
                Analytics.transformer_id == asset_id,
            )
        )
        == 0
    )


def test_failed_chunk_rolls_back_only_uncommitted_rows(
    ingestion_session: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.ingestion_service as service

    monkeypatch.setattr(service, "CHUNK_SIZE", 2)
    original = service.ingest_record
    calls = 0

    def fail_third(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("database unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "ingest_record", fail_third)
    with pytest.raises(RuntimeError):
        ingest_batch(ingestion_session, [make_record(asset_id, value) for value in range(4)])
    run = ingestion_session.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1))
    assert run.status == "FAILED"
    assert run.inserted_count == 2
    assert (
        ingestion_session.scalar(
            select(func.count())
            .select_from(Telemetry)
            .where(
                Telemetry.transformer_id == asset_id,
            )
        )
        == 2
    )
