import json
from datetime import UTC, datetime, timedelta
from statistics import median
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app


def test_million_row_dashboard_timings(db: Session) -> None:
    asset = "TX-million-" + uuid4().hex
    db.execute(text("INSERT INTO transformers(id,name) VALUES (:asset,:asset)"), {"asset": asset})
    start = perf_counter()
    db.execute(
        text("""
        INSERT INTO telemetry(transformer_id,timestamp,oil_temperature,oil_level,
            current_l1,current_l2,current_l3,phase_voltage_l1,phase_voltage_l2,phase_voltage_l3,
            oil_temp_alarm,oil_temp_trip,magnetic_oil_gauge_alarm,source_name,
            is_missing_critical,data_quality_score,schema_version)
        SELECT :asset, TIMESTAMPTZ '2026-01-01 00:00:00+00' + value * INTERVAL '1 second',
            42,8,0,0,0,0,0,0,0,0,0,'test-only',false,11.0/21,'1.0.0'
        FROM generate_series(0,999999) AS value
    """),
        {"asset": asset},
    )
    telemetry_load = perf_counter() - start
    start = perf_counter()
    db.execute(
        text("""
        INSERT INTO analytics(telemetry_id,transformer_id,timestamp,inference_status,
            health_index,fault_risk,anomaly_score,maintenance_priority,
            schema_version,feature_version,model_version)
        SELECT id,transformer_id,timestamp,'OK',90,0.05,0.1,'NORMAL','1.0.0','1.0.0','test-only'
        FROM telemetry WHERE transformer_id=:asset
    """),
        {"asset": asset},
    )
    analytics_load = perf_counter() - start
    db.execute(text("ANALYZE telemetry"))
    db.execute(text("ANALYZE analytics"))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    end = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=999999)
    params = {"from": (end - timedelta(hours=24)).isoformat(), "to": end.isoformat(), "limit": 500}
    queries = {
        "telemetry_24h": ("telemetry", params),
        "latest": ("latest", {}),
        "trends_24h_4_signals": (
            "trends",
            {
                "anchor": "latest",
                "window": "24h",
                "signals": "oil_temperature,current_l1,health_index,fault_risk",
            },
        ),
        "health_24h": ("health", params),
    }
    measurements = {}
    with TestClient(app) as client:
        for name, (suffix, query) in queries.items():
            samples = []
            for _ in range(5):
                start = perf_counter()
                response = client.get(f"/api/v1/transformers/{asset}/{suffix}", params=query)
                samples.append((perf_counter() - start) * 1000)
                assert response.status_code == 200
                if suffix in ("telemetry", "health"):
                    assert response.json()["total"] == 86401
                    assert len(response.json()["items"]) == 500
            measurements[name] = {
                "cold_ms": round(samples[0], 3),
                "median_ms": round(median(samples), 3),
                "max_ms": round(max(samples), 3),
            }
    print(
        "READ_BENCHMARK "
        + json.dumps(
            {
                "telemetry_rows": 1000000,
                "analytics_rows": 1000000,
                "telemetry_load_seconds": round(telemetry_load, 3),
                "analytics_load_seconds": round(analytics_load, 3),
                "timings": measurements,
            }
        )
    )
