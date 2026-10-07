"""Verify the isolated Compose demo through HTTP, MQTT, reset and a second seed."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import paho.mqtt.client as mqtt

from app.schemas.telemetry import TelemetryIn
from examples.client import TwinClient
from scripts.seed_demo import generate_records, seed_http, values_hash

BACKEND = Path(__file__).resolve().parents[1]


def compose(*args: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.backend.yml", *args],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def check_state(client: httpx.Client) -> dict[str, Any]:
    for path in ("/health", "/health/ready"):
        response = client.get(path)
        response.raise_for_status()
        assert response.json()["status"] in ("ok", "ready")
    latest = client.get("/api/v1/transformers/TX-001/latest").json()
    assert latest["demo_mode"] and latest["analytics"]["health_index"] == 90
    assert latest["transformer"]["name"] == "Demo transformer"
    assert latest["transformer"]["rated_power_kva"] is None
    pages = {}
    for suffix in ("telemetry", "health", "analytics", "alerts", "maintenance"):
        response = client.get(
            f"/api/v1/transformers/TX-001/{suffix}", params={"anchor": "latest", "limit": 5000}
        )
        response.raise_for_status()
        pages[suffix] = response.json()
    telemetry = [
        TelemetryIn.model_validate({key: row[key] for key in TelemetryIn.model_fields})
        for row in pages["telemetry"]["items"]
    ]
    assert len(telemetry) == pages["telemetry"]["total"] == 2000
    assert values_hash(telemetry) == values_hash(generate_records())
    alerts = pages["alerts"]["items"]
    alarm = next(row for row in alerts if row["alert_type"] == "OIL_TEMP_ALARM")
    trip = next(row for row in alerts if row["alert_type"] == "OIL_TEMP_TRIP")
    assert alarm["timestamp"] < trip["timestamp"]
    assert alarm["severity"] == "WARNING" and trip["severity"] == "CRITICAL"
    assert all(row["status"] == "RESOLVED" and row["resolved_at"] for row in alerts)
    assert latest["open_alerts_count"] == 0
    priorities = [row["priority"] for row in pages["maintenance"]["items"]]
    assert priorities == ["PLAN", "URGENT"]
    health = [row["health_index"] for row in pages["health"]["items"]]
    assert (
        health[0] == health[-1] == 90 and min(value for value in health if value is not None) == 25
    )
    assert None in health
    return {
        "counts": {name: page["total"] for name, page in pages.items()},
        "telemetry_values_sha256": values_hash(telemetry),
        "health_path": [90, 55, 25, 90],
        "insufficient_rows": health.count(None),
        "resolved_alerts": len(alerts),
        "maintenance_priorities": priorities,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--mqtt-port", type=int, default=51885)
    args = parser.parse_args()
    initial = json.loads(compose("exec", "-T", "backend", "python", "scripts/seed_demo.py"))
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        first = check_state(client)
        duplicate = seed_http(client, generate_records())
        assert duplicate["inserted_count"] == 0 and duplicate["duplicate_count"] == 2000
        assert duplicate["alerts_created"] == duplicate["maintenance_created"] == 0
        assert client.post("/api/v1/admin/demo/reset").status_code == 404
        status = client.get("/api/v1/ingest/mqtt/status").json()
        assert status["enabled"] and status["connected"]
        message = generate_records(2001)[-1].model_copy(
            update={"source_name": "mqtt-simulator", "scenario_id": "SCN_MQTT_CHECK"}
        )
        publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="demo-verification")
        publisher.connect("127.0.0.1", args.mqtt_port)
        publisher.loop_start()
        try:
            delivery = publisher.publish(
                "transformer/TX-001/telemetry", message.model_dump_json(), qos=1
            )
            delivery.wait_for_publish(timeout=10)
            assert delivery.is_published()
        finally:
            publisher.disconnect()
            publisher.loop_stop()
        deadline = monotonic() + 15
        while monotonic() < deadline:
            status = client.get("/api/v1/ingest/mqtt/status").json()
            if status["ingested_count"] >= 1:
                break
            sleep(0.1)
        assert status["ingested_count"] >= 1 and status["error_count"] == 0
        latest = client.get("/api/v1/transformers/TX-001/latest").json()
        assert latest["telemetry"]["scenario_id"] == "SCN_MQTT_CHECK"
        reset = json.loads(
            compose("exec", "-T", "backend", "python", "scripts/reset_demo.py", "--yes")
        )
        latest = client.get("/api/v1/transformers/TX-001/latest").json()
        assert latest["telemetry"] is None and latest["analytics"] is None
        for suffix in ("telemetry", "analytics", "alerts", "maintenance"):
            assert client.get(f"/api/v1/transformers/TX-001/{suffix}").json()["total"] == 0
        assert client.get("/api/v1/scenarios").json()["total"] == 0
        assert (
            client.get("/api/v1/ingest/mqtt/status").json()["ingested_count"]
            == status["ingested_count"]
        )
        second_seed = seed_http(client, generate_records())
        second = check_state(client)
        assert first == second
    with TwinClient(args.base_url) as twin:
        assert twin.latest().demo_mode
        assert twin.telemetry(limit=1).total == twin.health(limit=1).total == 2000
        assert twin.analytics(limit=1).total == 2000
        assert twin.alerts().total == first["counts"]["alerts"]
        assert twin.maintenance().total == 2
        assert twin.trends().signals
    identity = compose("exec", "-T", "backend", "id").strip()
    assert "uid=10001" in identity
    dependencies = compose(
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        "import importlib.util; print(importlib.util.find_spec('pytest')); "
        "print(importlib.util.find_spec('ruff'))",
    )
    assert dependencies.splitlines() == ["None", "None"]
    result = {
        "initial_seed": initial,
        "duplicate_seed": duplicate,
        "reset": reset,
        "second_seed": second_seed,
        "determinism": first,
        "mqtt_ingested": True,
        "runtime_identity": identity,
        "dev_dependencies_absent": True,
        "fresh_stack_health_and_readiness": True,
    }
    path = BACKEND / "docs" / "demo-verification.json"
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
