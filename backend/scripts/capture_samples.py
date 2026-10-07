"""Capture real demo API responses and regenerate the API endpoint reference."""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from scripts.seed_demo import START, generate_records

BACKEND = Path(__file__).resolve().parents[1]


def capture(client: httpx.Client, asset: str) -> dict[str, Any]:
    samples: dict[str, Any] = {}

    def request(label: str, method: str, path: str, **kwargs: Any) -> Any:
        response = client.request(method, path, **kwargs)
        # Expected error responses are also captured, never synthesized.
        if response.status_code >= 500:
            response.raise_for_status()
        body = response.json()
        samples[label] = {
            "method": method,
            "path": path,
            "status": response.status_code,
            "body": body,
        }
        return body

    request("liveness", "GET", "/health")
    request("ready", "GET", "/health/ready")
    request("transformers", "GET", "/api/v1/transformers", params={"limit": 5})
    request("transformer", "GET", f"/api/v1/transformers/{asset}")
    latest = request("latest", "GET", f"/api/v1/transformers/{asset}/latest")
    if latest.get("telemetry") is None:
        raise ValueError("Seed the demo before capturing samples")
    for suffix in ("telemetry", "health", "analytics", "alerts", "maintenance"):
        request(
            suffix,
            "GET",
            f"/api/v1/transformers/{asset}/{suffix}",
            params={"anchor": "latest", "limit": 3},
        )
    request(
        "telemetry_projection",
        "GET",
        f"/api/v1/transformers/{asset}/telemetry",
        params={"anchor": "latest", "fields": "oil_temperature,current_l1,source_name", "limit": 3},
    )
    request(
        "trends",
        "GET",
        f"/api/v1/transformers/{asset}/trends",
        params={
            "anchor": "latest",
            "window": "24h",
            "signals": "oil_temperature,current_l1,health_index,fault_risk",
        },
    )
    request("scenarios", "GET", "/api/v1/scenarios")
    request("mqtt_status", "GET", "/api/v1/ingest/mqtt/status")
    request("not_found", "GET", "/api/v1/transformers/TX-NOT-PRESENT")
    request("validation_error", "GET", f"/api/v1/transformers/{asset}/health", params={"limit": 0})
    for scenario, index in (
        ("healthy", 0),
        ("stress", 1000),
        ("alarm", 1450),
        ("trip", 1750),
        ("recovery", 1999),
    ):
        timestamp = (START + timedelta(seconds=index * 30)).isoformat()
        request(
            "segment_" + scenario,
            "GET",
            f"/api/v1/transformers/{asset}/telemetry",
            params={
                "from": timestamp,
                "to": (START + timedelta(seconds=index * 30 + 1)).isoformat(),
                "limit": 1,
            },
        )
    # Write/lifecycle examples use a separate asset and leave the seeded asset untouched.
    demo_asset = "TX-CAPTURE"
    response = client.get(f"/api/v1/transformers/{demo_asset}")
    if response.status_code != 404:
        raise ValueError(
            "TX-CAPTURE exists; reset including transformers and reseed before capture"
        )
    request(
        "transformer_create",
        "POST",
        "/api/v1/transformers",
        json={"id": demo_asset, "name": "Sample capture asset"},
    )
    request(
        "transformer_patch",
        "PATCH",
        f"/api/v1/transformers/{demo_asset}",
        json={"name": "Sample capture asset updated"},
    )
    records = generate_records(60, demo_asset)
    alarm = next(row for row in records if row.oil_temp_alarm == 1)
    trip = next(row for row in records if row.oil_temp_trip == 1)
    request("telemetry_post", "POST", "/api/v1/telemetry", json=alarm.model_dump(mode="json"))
    request("telemetry_duplicate", "POST", "/api/v1/telemetry", json=alarm.model_dump(mode="json"))
    alerts = client.get(
        f"/api/v1/transformers/{demo_asset}/alerts", params={"anchor": "latest"}
    ).json()
    alert_id = next(row["id"] for row in alerts["items"] if row["alert_type"] == "OIL_TEMP_ALARM")
    request("alert_get", "GET", f"/api/v1/alerts/{alert_id}")
    request("alert_acknowledge", "PATCH", f"/api/v1/alerts/{alert_id}/acknowledge")
    request("alert_resolve", "PATCH", f"/api/v1/alerts/{alert_id}/resolve")
    request(
        "telemetry_batch",
        "POST",
        "/api/v1/telemetry/batch",
        json={"records": [trip.model_dump(mode="json")]},
    )
    maintenance = client.get(
        f"/api/v1/transformers/{demo_asset}/maintenance", params={"anchor": "latest"}
    ).json()
    maintenance_id = maintenance["items"][0]["id"]
    request("maintenance_get", "GET", f"/api/v1/maintenance/{maintenance_id}")
    request(
        "maintenance_patch",
        "PATCH",
        f"/api/v1/maintenance/{maintenance_id}",
        json={"status": "DONE"},
    )
    replay = request(
        "replay_start",
        "POST",
        "/api/v1/simulate/replay",
        json={
            "transformer_id": demo_asset,
            "speed_multiplier": 0,
            "records": [row.model_dump(mode="json") for row in records[-5:]],
            "source_name": "replay-samples",
        },
    )
    request("replay_status", "GET", f"/api/v1/simulate/replay/{replay['run_id']}")
    request("reset_disabled", "POST", "/api/v1/admin/demo/reset")
    return samples


def endpoint_table(openapi: dict[str, Any]) -> str:
    lines = [
        "| Method / path | Parameters and defaults | Success response |",
        "| --- | --- | --- |",
    ]
    for path, methods in openapi["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "patch", "delete", "put"):
                continue
            params = []
            for param in operation.get("parameters", []):
                schema = param.get("schema", {})
                default = (
                    json.dumps(schema["default"])
                    if "default" in schema
                    else ("required" if param.get("required") else "optional")
                )
                params.append(f"{param['name']} ({param['in']}, {default})")
            if "requestBody" in operation:
                content = operation["requestBody"]["content"]["application/json"]["schema"]
                params.append("JSON body: " + content.get("$ref", "object").split("/")[-1])
            statuses = ", ".join(
                status for status in operation["responses"] if status.startswith("2")
            )
            lines.append(
                f"| {method.upper()} `{path}` | {'; '.join(params) or 'none'} | {statuses} |"
            )
    return "\n".join(lines)


def write_reference(samples: dict[str, Any], openapi: dict[str, Any]) -> None:
    out = BACKEND / "docs" / "samples"
    out.mkdir(exist_ok=True)
    (out / "api-responses.json").write_text(
        json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    notes = (BACKEND / "docs" / "api-notes.md").read_text(encoding="utf-8")
    sections = [
        "# Consolidated backend API",
        notes,
        "## All API operations",
        endpoint_table(openapi),
        "## Captured demo responses",
        "These JSON values were captured from the seeded Compose demo "
        "by scripts/capture_samples.py. "
        "The full bodies are in [samples/api-responses.json](samples/api-responses.json). "
        "Page examples retain the first item; trends retain their first populated bucket. "
        "These are real response selections. Write samples use TX-CAPTURE; TX-001 is unchanged.",
    ]
    for label in (
        "liveness",
        "ready",
        "latest",
        "telemetry_projection",
        "health",
        "alerts",
        "maintenance",
        "segment_alarm",
        "segment_trip",
        "telemetry_post",
        "telemetry_duplicate",
        "telemetry_batch",
        "replay_start",
        "mqtt_status",
        "validation_error",
    ):
        body = samples[label]["body"]
        if isinstance(body, dict) and "items" in body:
            body = body | {"items": body["items"][:1]}
        sections += [
            f"### {label} (HTTP {samples[label]['status']})",
            "```json\n" + json.dumps(body, indent=2) + "\n```",
        ]
    trend = samples["trends"]["body"]
    trend = trend | {
        "signals": {
            name: [next((row for row in values if row["count"]), values[0])]
            for name, values in trend["signals"].items()
        },
        "protection_events": trend["protection_events"][:1],
    }
    sections += [
        "### Four-signal trends (selected buckets)",
        "```json\n" + json.dumps(trend, indent=2) + "\n```",
    ]
    (BACKEND / "docs" / "api.md").write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--transformer-id", default="TX-001")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120) as client:
        samples = capture(client, args.transformer_id)
        response = client.get("/openapi.json")
        response.raise_for_status()
        write_reference(samples, response.json())
    print("Captured API responses and regenerated docs/api.md")


if __name__ == "__main__":
    main()
