import json
import re
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from examples.client import TwinClient
from scripts.seed_demo import generate_records, seed_in_process
from tests.hardening.test_guards import EXCLUDED, RAW

BACKEND = Path(__file__).resolve().parents[2]


def test_operational_examples_and_scripts_use_only_canonical_names_and_proxy_wording() -> None:
    paths = list((BACKEND / "scripts").glob("*.ps1"))
    paths += list((BACKEND / "docker").glob("*"))
    paths += list((BACKEND / "examples").glob("*"))
    paths += [
        BACKEND / "Dockerfile",
        BACKEND / "docker-compose.backend.yml",
        BACKEND / "CHANGELOG.md",
    ]
    paths += list((BACKEND / "docs" / "samples").glob("*.json"))
    paths += [BACKEND / "docs" / "demo-verification.json"]
    prohibited = ["confirmed" + " fault", "fault" + " detected", "confirmed" + " failure"]
    failures = []
    for path in paths:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if (
                RAW.search(line)
                or EXCLUDED.search(line)
                or any(word in line.casefold() for word in prohibited)
            ):
                failures.append(f"{path.relative_to(BACKEND)}:{number}")
    assert not failures, "New operational/example guard failures: " + ", ".join(failures)


def test_api_reference_and_http_requests_cover_every_operation() -> None:
    api = (BACKEND / "docs" / "api.md").read_text(encoding="utf-8")
    requests = (BACKEND / "examples" / "requests.http").read_text(encoding="utf-8")
    for path, methods in create_app().openapi()["paths"].items():
        for method in methods:
            if method not in ("get", "post", "patch", "delete", "put"):
                continue
            assert f"{method.upper()} `{path}`" in api
            assert f"# {method.upper()} {path}" in requests
    assert "X-Admin-Token" in requests and "anchor=latest" in requests


def test_captured_demo_samples_have_real_chain_and_error_contract() -> None:
    samples = json.loads((BACKEND / "docs" / "samples" / "api-responses.json").read_text())
    assert samples["liveness"]["body"]["status"] == "ok"
    assert samples["ready"]["body"]["status"] == "ready"
    assert samples["latest"]["body"]["demo_mode"]
    assert samples["latest"]["body"]["analytics"]["health_index"] == 90
    assert samples["segment_alarm"]["body"]["items"][0]["oil_temp_alarm"] == 1
    assert samples["segment_trip"]["body"]["items"][0]["oil_temp_trip"] == 1
    assert samples["telemetry_duplicate"]["body"]["duplicate"]
    assert samples["telemetry_post"]["body"]["analytics"]["maintenance_priority"] == "PLAN"
    assert samples["validation_error"]["status"] == 422
    assert samples["validation_error"]["body"]["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        "request_id" in row for row in samples["validation_error"]["body"]["error"]["details"]
    )
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        json.loads((BACKEND / "docs" / "demo-verification.json").read_text())["determinism"][
            "telemetry_values_sha256"
        ],
    )


def test_typed_client_reads_seed_and_preserves_null_projection(
    client: TestClient,
    db: Session,
) -> None:
    asset = "TX-client-" + uuid4().hex
    seed_in_process(db, generate_records(60, asset))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(
            ("/telemetry", "/health", "/analytics", "/alerts", "/maintenance", "/trends")
        ):
            assert request.url.params["anchor"] == "latest"
        response = client.get(request.url.path, params=request.url.params.multi_items())
        return httpx.Response(response.status_code, json=response.json())

    with TwinClient("http://demo") as twin:
        twin._client.close()
        twin._client = httpx.Client(base_url="http://demo", transport=httpx.MockTransport(handler))
        assert twin.latest(asset).demo_mode
        assert twin.telemetry(asset, limit=1).total == 60
        projection = twin.telemetry(asset, limit=1, offset=12, fields="oil_temperature")
        assert projection.items[0].oil_temperature is None
        assert projection.items[0].transformer_id is None
        assert twin.health(asset, limit=1).total == 60
        assert twin.analytics(asset, limit=1).total == 60
        assert twin.alerts(asset, status="RESOLVED", severity="CRITICAL").items
        assert twin.maintenance(asset, status="OPEN").total == 2
        assert twin.trends(asset).signals
