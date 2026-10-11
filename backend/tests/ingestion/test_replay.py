from time import perf_counter
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Analytics, Telemetry

from .conftest import make_record


@pytest.fixture
def replay_asset(ingest_client, asset_id):
    destination = asset_id + '-replay'
    assert ingest_client.post('/api/v1/transformers', json={'id': destination, 'name': 'Isolated replay'}).status_code == 201
    return destination


def test_replay_uses_shared_ingestion_and_reports_completed(
    replay_asset: str,
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.replay_service as replay

    original = replay.ingest_record
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(replay, "ingest_record", counted)
    started = perf_counter()
    response = ingest_client.post(
        "/api/v1/simulate/replay",
        json={
            "transformer_id": asset_id,
            'replay_transformer_id': replay_asset,
            "source_name": "replay-test",
            "speed_multiplier": 0,
            "records": [make_record(asset_id, second) for second in [10000, 0]],
        },
    )
    elapsed = perf_counter() - started
    assert response.status_code == 202
    assert elapsed < 5
    assert calls == 2
    status = ingest_client.get(f"/api/v1/simulate/replay/{response.json()['run_id']}")
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "COMPLETED"
    assert data["row_count"] == data["inserted_count"] == 2
    assert data["finished_at"] is not None
    rows = ingestion_session.scalars(
        select(Telemetry).where(Telemetry.transformer_id == replay_asset)
    ).all()
    assert all(row.source_name == "replay-test" for row in rows)
    assert all(row.acquisition['origin_transformer_id'] == asset_id for row in rows)


def test_replay_gaps_are_scaled_and_capped(
    replay_asset: str,
    ingest_client: TestClient,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.replay_service as replay

    delays: list[float] = []
    monkeypatch.setattr(replay, "sleep", delays.append)
    response = ingest_client.post(
        "/api/v1/simulate/replay",
        json={
            "source_name": "scaled-replay",
            'replay_transformer_id': replay_asset,
            "speed_multiplier": 2,
            "records": [make_record(asset_id, second) for second in [0, 4, 100]],
        },
    )
    assert response.status_code == 202
    assert delays == [2, 5]


def test_stored_replay_preserves_live_rows_and_analysis(
    replay_asset: str,
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
) -> None:
    ingest_client.post("/api/v1/telemetry?run_ml=false", json=make_record(asset_id, 0))
    existing = ingest_client.post("/api/v1/telemetry", json=make_record(asset_id, 1)).json()
    payload = {
        "transformer_id": asset_id,
        'replay_transformer_id': replay_asset,
        "source_name": "stored-replay",
        "from_stored": {"start": "2026-10-06T00:00:00Z", "end": "2026-10-06T00:00:01Z"},
    }
    response = ingest_client.post("/api/v1/simulate/replay", json=payload)
    status = ingest_client.get(f"/api/v1/simulate/replay/{response.json()['run_id']}").json()
    assert status["status"] == "COMPLETED"
    assert status['inserted_count'] == 2
    assert status['duplicate_count'] == 0
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
    assert (
        ingestion_session.scalar(
            select(func.count())
            .select_from(Analytics)
            .where(
                Analytics.transformer_id == asset_id,
            )
        )
        == 1
    )
    persisted = ingestion_session.scalar(
        select(Analytics).where(
            Analytics.telemetry_id == existing["telemetry_id"],
        )
    )
    first_id = persisted.id
    second = ingest_client.post('/api/v1/simulate/replay', json=payload)
    # A new run is different semantic lineage under the same destination/time.
    assert ingest_client.get(f"/api/v1/simulate/replay/{second.json()['run_id']}").json()['status'] == 'FAILED'
    ingestion_session.expire_all()
    assert ingestion_session.get(Analytics, first_id).telemetry_id == existing["telemetry_id"]


def test_replay_failure_sets_failed_status(
    replay_asset: str,
    ingest_client: TestClient,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.replay_service as replay

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("forced replay failure")

    monkeypatch.setattr(replay, "ingest_record", fail)
    response = ingest_client.post(
        "/api/v1/simulate/replay",
        json={
            "source_name": "failure-test",
            'replay_transformer_id': replay_asset,
            "records": [make_record(asset_id, 0)],
        },
    )
    status = ingest_client.get(f"/api/v1/simulate/replay/{response.json()['run_id']}").json()
    assert status["status"] == "FAILED"
    assert status["finished_at"] is not None
    assert status["inserted_count"] == 0


def test_replay_unknown_run_returns_standard_error(ingest_client: TestClient) -> None:
    response = ingest_client.get("/api/v1/simulate/replay/999999999")
    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message", "details"}
