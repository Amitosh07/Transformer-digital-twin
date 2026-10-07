"""Deterministic canonical demo data through the existing batch ingestion path."""

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import demo_repo, transformer_repo
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerIn
from app.services.ingestion_service import ingest_batch
from scripts.reset_demo import run_reset

START = datetime(2026, 1, 1, tzinfo=UTC)
NAMEPLATE = (
    "rated_power_kva",
    "rated_voltage_hv",
    "rated_voltage_lv",
    "rated_current_a",
    "cooling_class",
    "oil_type",
)


def generate_records(rows: int = 2000, transformer_id: str = "TX-001") -> list[TelemetryIn]:
    if rows < 1:
        raise ValueError("--rows must be positive")
    rng = random.Random(42)
    healthy, stress = rows * 4 // 10, rows * 3 // 10
    fault = rows - healthy - stress
    recovery = min(fault, max(5, fault // 5))
    active = fault - recovery
    alarm_length = active // 2
    energy = 0.0
    records = []
    for index in range(rows):
        alarm = trip = 0
        if index < healthy:
            scenario, level = "SCN_HEALTHY", 0.0
        elif index < healthy + stress:
            scenario = "SCN_STRESS"
            level = (index - healthy) / max(stress - 1, 1)
        else:
            scenario = "SCN_FAULT"
            local = index - healthy - stress
            if local < active:
                level = 1.0 + 0.5 * local / max(active - 1, 1)
                alarm = int(local < alarm_length)
                trip = int(local >= alarm_length)
            else:
                level = 0.0
        current = 85 + 95 * level + rng.uniform(-0.5, 0.5)
        voltage = 230 - 3 * level + rng.uniform(-0.2, 0.2)
        currents = [current * (1 + rng.uniform(-0.003, 0.003)) for _ in range(3)]
        voltages = [voltage * (1 + rng.uniform(-0.001, 0.001)) for _ in range(3)]
        pf = 0.95
        apparent = sum(v * i for v, i in zip(voltages, currents, strict=True)) / 1000
        power = apparent * pf
        energy += power * 30 / 3600
        dropout = healthy // 2 <= index < healthy // 2 + max(1, healthy // 80) and index < healthy
        values: dict[str, Any] = {
            "transformer_id": transformer_id,
            "timestamp": START + timedelta(seconds=30 * index),
            "source_name": "seed",
            "scenario_id": scenario,
            "neutral_current": round(max(currents) - min(currents), 6),
            "oil_temperature": None if dropout else round(42 + 24 * level, 6),
            "winding_temperature": round(45 + 28 * level, 6),
            "ambient_temperature": 22.0,
            "oil_level": 8.0,
            "oil_temp_alarm": alarm,
            "oil_temp_trip": trip,
            "magnetic_oil_gauge_alarm": 0,
            "apparent_power_total": round(apparent, 6),
            "active_power_total": round(power, 6),
            "reactive_power_total": round(apparent * math.sqrt(1 - pf * pf), 6),
            "energy_kwh": round(energy, 6),
        }
        for phase in range(1, 4):
            values[f"current_l{phase}"] = round(currents[phase - 1], 6)
            values[f"phase_voltage_l{phase}"] = round(voltages[phase - 1], 6)
            values[f"power_factor_l{phase}"] = pf
        records.append(TelemetryIn.model_validate(values))
    return records


def values_hash(records: list[TelemetryIn]) -> str:
    payload = [
        row.model_dump(mode="json") for row in sorted(records, key=lambda row: row.timestamp)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def seed_in_process(
    session: Session,
    records: list[TelemetryIn],
    *,
    nameplate: dict[str, Any] | None = None,
    run_ml: bool = True,
) -> dict[str, Any]:
    asset = records[0].transformer_id
    payload = TransformerIn(id=asset, name="Demo transformer", **(nameplate or {}))
    existing = transformer_repo.get(session, asset)
    if existing is None:
        transformer_repo.create(session, payload)
    else:
        transformer_repo.patch(session, existing, {"name": payload.name} | (nameplate or {}))
    session.commit()
    before = demo_repo.summary(session, asset)
    inserted = duplicates = 0
    size = get_settings().max_batch_size
    for start in range(0, len(records), size):
        result = ingest_batch(
            session,
            [row.model_dump(mode="json") for row in records[start : start + size]],
            run_ml=run_ml,
            source_name="seed",
        )
        inserted += result.inserted_count
        duplicates += result.duplicate_count
    after = demo_repo.summary(session, asset)
    return after | {
        "inserted_count": inserted,
        "duplicate_count": duplicates,
        "alerts_created": after["alerts"] - before["alerts"],
        "maintenance_created": after["maintenance_records"] - before["maintenance_records"],
        "telemetry_values_sha256": values_hash(records),
    }


def http_summary(client: httpx.Client, asset: str, records: list[TelemetryIn]) -> dict[str, Any]:
    path = "/api/v1/transformers/" + quote(asset, safe="")
    # Explicit bounds retain earlier episodes even when the newest row is a recovery row.
    params = {
        "from": (records[0].timestamp - timedelta(seconds=1)).isoformat(),
        "to": (records[-1].timestamp + timedelta(seconds=1)).isoformat(),
        "limit": 1,
    }
    counts = {}
    for suffix in ("telemetry", "analytics", "alerts", "maintenance"):
        response = client.get(path + "/" + suffix, params=params)
        response.raise_for_status()
        counts["maintenance_records" if suffix == "maintenance" else suffix] = response.json()[
            "total"
        ]
    health = []
    offset = 0
    while True:
        response = client.get(path + "/health", params=params | {"limit": 500, "offset": offset})
        response.raise_for_status()
        page = response.json()
        health += [row["health_index"] for row in page["items"] if row["health_index"] is not None]
        offset += len(page["items"])
        if offset >= page["total"] or not page["items"]:
            break
    return counts | {
        "health_index_min": min(health, default=None),
        "health_index_max": max(health, default=None),
    }


def seed_http(
    client: httpx.Client,
    records: list[TelemetryIn],
    *,
    nameplate: dict[str, Any] | None = None,
    run_ml: bool = True,
) -> dict[str, Any]:
    asset = records[0].transformer_id
    path = "/api/v1/transformers/" + quote(asset, safe="")
    response = client.get(path)
    payload = TransformerIn(id=asset, name="Demo transformer", **(nameplate or {}))
    if response.status_code == 404:
        response = client.post("/api/v1/transformers", json=payload.model_dump(mode="json"))
        if response.status_code == 409:
            response = client.patch(path, json={"name": payload.name} | (nameplate or {}))
    else:
        response.raise_for_status()
        response = client.patch(path, json={"name": payload.name} | (nameplate or {}))
    response.raise_for_status()
    before = http_summary(client, asset, records)
    inserted = duplicates = 0
    # Respect this process's configured envelope cap; remote servers can set a smaller cap.
    size = min(500, get_settings().max_batch_size)
    for start in range(0, len(records), size):
        response = client.post(
            "/api/v1/telemetry/batch",
            params={"run_ml": run_ml, "source_name": "seed"},
            json={
                "records": [row.model_dump(mode="json") for row in records[start : start + size]]
            },
        )
        response.raise_for_status()
        summary = response.json()
        if summary["parse_error_count"] or summary["out_of_range_count"]:
            raise ValueError("Demo records rejected by remote schema")
        inserted += summary["inserted_count"]
        duplicates += summary["duplicate_count"]
    after = http_summary(client, asset, records)
    return after | {
        "scenarios": dict(Counter(row.scenario_id for row in records)),
        "inserted_count": inserted,
        "duplicate_count": duplicates,
        "alerts_created": after["alerts"] - before["alerts"],
        "maintenance_created": after["maintenance_records"] - before["maintenance_records"],
        "telemetry_values_sha256": values_hash(records),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--transformer-id", default="TX-001")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Required with --reset")
    parser.add_argument("--base-url")
    parser.add_argument("--no-ml", action="store_true")
    for name in NAMEPLATE:
        parser.add_argument(
            "--" + name.replace("_", "-"),
            type=str if name in ("cooling_class", "oil_type") else float,
        )
    args = parser.parse_args()
    try:
        records = generate_records(args.rows, args.transformer_id)
        nameplate = {
            name: getattr(args, name) for name in NAMEPLATE if getattr(args, name) is not None
        }
        TransformerIn(id=args.transformer_id, name="Demo transformer", **nameplate)
        if args.reset:
            run_reset(yes=args.yes, base_url=args.base_url)
        if args.base_url:
            with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120) as client:
                report = seed_http(client, records, nameplate=nameplate, run_ml=not args.no_ml)
        else:
            with SessionLocal() as session:
                report = seed_in_process(
                    session, records, nameplate=nameplate, run_ml=not args.no_ml
                )
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ValueError, httpx.HTTPError) as exc:
        parser.exit(
            1, f"Seed failed: {type(exc).__name__}: check arguments and service configuration\n"
        )


if __name__ == "__main__":
    main()
