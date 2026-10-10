import math
from collections import Counter
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Alert, Analytics, MaintenanceRecord, Telemetry, Transformer
from app.schemas.telemetry import TelemetryIn
from app.services.demo_service import reset_demo
from scripts.seed_demo import START, generate_records, seed_http, seed_in_process, values_hash


def stored_records(db: Session, asset: str) -> list[TelemetryIn]:
    rows = db.scalars(
        select(Telemetry).where(Telemetry.transformer_id == asset).order_by(Telemetry.timestamp)
    )
    return [
        TelemetryIn.model_validate({name: getattr(row, name) for name in TelemetryIn.model_fields})
        for row in rows
    ]


def test_generator_is_fixed_canonical_and_electrically_coherent() -> None:
    records = generate_records()
    assert records == generate_records()
    assert Counter(row.scenario_id for row in records) == {
        "SCN_HEALTHY": 800,
        "SCN_STRESS": 600,
        "SCN_FAULT": 600,
    }
    assert records[0].timestamp == START
    assert all(
        b.timestamp - a.timestamp == timedelta(seconds=30)
        for a, b in zip(records, records[1:], strict=False)
    )
    assert all(row.source_name == "seed" for row in records)
    assert sum(row.oil_temperature is None for row in records) == 10
    for row in records:
        apparent = (
            sum(
                getattr(row, f"phase_voltage_l{phase}") * getattr(row, f"current_l{phase}")
                for phase in range(1, 4)
            )
            / 1000
        )
        assert row.apparent_power_total == pytest.approx(apparent, abs=1e-5)
        assert row.active_power_total == pytest.approx(apparent * 0.95, abs=1e-5)
        assert row.reactive_power_total == pytest.approx(
            apparent * math.sqrt(1 - 0.95**2), abs=1e-5
        )
    assert records[1399].current_l1 > records[800].current_l1
    assert records[1399].oil_temperature > records[800].oil_temperature
    assert records[1399].active_power_total > records[800].active_power_total
    assert records[-1].oil_temp_alarm == records[-1].oil_temp_trip == 0


@pytest.mark.parametrize("rows", [1, 3, 19, 60, 2001])
def test_requested_size_and_custom_asset(rows: int) -> None:
    records = generate_records(rows, "TX-custom")
    assert len(records) == rows and all(row.transformer_id == "TX-custom" for row in records)
    assert values_hash(records) == values_hash(generate_records(rows, "TX-custom"))


@pytest.mark.parametrize("rows", [0, -1])
def test_bad_row_count(rows: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        generate_records(rows)


def test_seed_idempotent_reset_determinism_and_scenario_chain(db: Session) -> None:
    asset = "TX-seed-" + uuid4().hex
    records = generate_records(60, asset)
    first = seed_in_process(db, records)
    assert first["inserted_count"] == 60 and first["duplicate_count"] == 0
    assert first["health_index_min"] == 25 and first["health_index_max"] == 90
    row = db.get(Transformer, asset)
    assert row.name == "Demo transformer"
    assert all(
        getattr(row, name) is None
        for name in (
            "rated_power_kva",
            "rated_voltage_hv",
            "rated_voltage_lv",
            "rated_current_a",
            "cooling_class",
            "oil_type",
        )
    )
    first_hash = values_hash(stored_records(db, asset))
    duplicate = seed_in_process(db, records)
    assert duplicate["inserted_count"] == 0 and duplicate["duplicate_count"] == 60
    assert duplicate["alerts_created"] == duplicate["maintenance_created"] == 0
    alerts = list(db.scalars(select(Alert).where(Alert.transformer_id == asset)))
    assert {row.alert_type for row in alerts} >= {"OIL_TEMP_ALARM", "OIL_TEMP_TRIP"}
    assert all(row.status == "RESOLVED" and row.resolved_at for row in alerts)
    trip = next(row for row in alerts if row.alert_type == "OIL_TEMP_TRIP")
    assert trip.severity == "CRITICAL"
    maintenance = list(
        db.scalars(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.transformer_id == asset)
            .order_by(MaintenanceRecord.timestamp)
        )
    )
    assert [row.priority for row in maintenance] == ["PLAN", "URGENT"]
    health = list(
        db.scalars(
            select(Analytics.health_index)
            .where(Analytics.transformer_id == asset)
            .order_by(Analytics.timestamp)
        )
    )
    assert health[0] == health[-1] == 90 and None in health
    reset_demo(db, Settings(_env_file=None), yes=True)
    second = seed_in_process(db, records)
    assert first == second
    assert values_hash(stored_records(db, asset)) == first_hash == values_hash(records)


def test_seed_no_ml_and_explicit_nameplate(db: Session) -> None:
    asset = "TX-nameplate-" + uuid4().hex
    records = generate_records(10, asset)
    result = seed_in_process(
        db,
        records,
        nameplate={"rated_power_kva": 123.0, "cooling_class": "user configured"},
        run_ml=False,
    )
    assert result["analytics"] == result["alerts_created"] == result["maintenance_created"] == 0
    assert result["health_index_min"] is None
    assert db.get(Transformer, asset).rated_power_kva == 123.0
    seed_in_process(db, records, run_ml=False)
    assert db.get(Transformer, asset).rated_power_kva == 123.0


def test_http_seed_uses_same_service_and_is_idempotent(client: TestClient, db: Session) -> None:
    asset = "TX-http-seed-" + uuid4().hex
    records = generate_records(60, asset)
    first = seed_http(client, records)
    second = seed_http(client, records)
    assert first["inserted_count"] == 60 and second["duplicate_count"] == 60
    assert first["health_index_min"] == 25 and first["health_index_max"] == 90
    assert second["alerts_created"] == second["maintenance_created"] == 0
    assert values_hash(stored_records(db, asset)) == values_hash(records)
