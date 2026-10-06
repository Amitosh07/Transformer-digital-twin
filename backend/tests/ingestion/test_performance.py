import json
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Analytics, Telemetry

from .conftest import make_record


def test_ten_thousand_stub_rows_and_idempotent_reload(
    ingest_client: TestClient,
    asset_id: str,
    ingestion_session: Session,
) -> None:
    rows = [make_record(asset_id, second) for second in range(10000)]
    started = perf_counter()
    first = ingest_client.post("/api/v1/telemetry/batch", json={"records": rows})
    elapsed = perf_counter() - started
    assert first.status_code == 200
    summary = first.json()
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
        "row_count": 10000,
        "inserted_count": 10000,
        "duplicate_count": 0,
        "parse_error_count": 0,
        "out_of_range_count": 0,
    }
    started = perf_counter()
    second = ingest_client.post("/api/v1/telemetry/batch", json={"records": rows})
    duplicate_elapsed = perf_counter() - started
    assert second.status_code == 200
    assert second.json()["inserted_count"] == 0
    assert second.json()["duplicate_count"] == 10000
    for model in [Telemetry, Analytics]:
        assert (
            ingestion_session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.transformer_id == asset_id,
                )
            )
            == 10000
        )
    print(
        "BENCHMARK "
        + json.dumps(
            {
                "elapsed_seconds": round(elapsed, 3),
                "duplicate_elapsed_seconds": round(duplicate_elapsed, 3),
                "summary": summary,
                "duplicate_summary": second.json(),
            }
        )
    )
