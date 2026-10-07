from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Alert, Analytics, IngestionRun, MaintenanceRecord, Telemetry, Transformer
from app.repositories import demo_repo
from app.services.demo_service import reset_demo
from scripts import reset_demo as reset_script
from scripts.seed_demo import generate_records, seed_in_process


@pytest.mark.parametrize("env", ["production", "PRODUCTION", " production "])
def test_reset_refuses_production_before_opening_database(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("ENV", env)
    get_settings.cache_clear()

    def unexpected() -> None:
        raise AssertionError("Reset must not open a database in production")

    monkeypatch.setattr(reset_script, "SessionLocal", unexpected)
    with pytest.raises(ValueError, match="production"):
        reset_script.run_reset(yes=True)


def test_reset_requires_yes_before_opening_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reset_script, "SessionLocal", lambda: pytest.fail("DB must not open"))
    with pytest.raises(ValueError, match="--yes"):
        reset_script.run_reset(yes=False)


@pytest.mark.parametrize("include", [False, True])
def test_fk_safe_reset_clears_all_requested_tables(db: Session, include: bool) -> None:
    asset = "TX-reset-" + uuid4().hex
    seed_in_process(db, generate_records(60, asset))
    result = reset_demo(db, Settings(_env_file=None), yes=True, include_transformers=include)
    assert result.deleted["telemetry"] >= 60 and result.deleted["analytics"] >= 60
    for model in (Alert, Analytics, Telemetry, MaintenanceRecord, IngestionRun):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert (db.get(Transformer, asset) is None) == include


def test_reset_rolls_back_partial_delete_on_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = "TX-atomic-" + uuid4().hex
    seed_in_process(db, generate_records(60, asset))
    before = demo_repo.summary(db, asset)
    db.commit()

    def fail(session: Session, include: bool) -> dict[str, int]:
        session.execute(delete(MaintenanceRecord))
        raise RuntimeError("simulated reset failure")

    monkeypatch.setattr(demo_repo, "delete_demo_data", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        reset_demo(db, Settings(_env_file=None), yes=True)
    assert demo_repo.summary(db, asset) == before


def test_reset_endpoint_disabled_by_default(client: TestClient) -> None:
    response = client.post("/api/v1/admin/demo/reset", headers={"X-Admin-Token": "anything"})
    assert response.status_code == 404
    assert response.json()["error"]["details"]["request_id"]


@pytest.mark.parametrize(
    "configured,provided,env,expected",
    [
        ("", None, "development", 403),
        ("secret", None, "development", 403),
        ("secret", "wrong", "development", 403),
        ("secret", "secret", "production", 403),
        ("secret", "secret", "development", 200),
    ],
)
def test_reset_endpoint_token_and_production_safety(
    client: TestClient,
    db: Session,
    configured: str,
    provided: str | None,
    env: str,
    expected: int,
) -> None:
    app = client.app
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, env=env, demo_reset_enabled=True, demo_admin_token=configured
    )
    headers = {} if provided is None else {"X-Admin-Token": provided}
    response = client.post("/api/v1/admin/demo/reset", headers=headers)
    assert response.status_code == expected
    assert configured not in response.text if configured else True
    if expected == 200:
        assert "deleted" in response.json() and "transformers" not in response.json()["deleted"]


def test_cli_http_reset_uses_token_and_include_option(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Admin-Token"] == "configured-demo-token"
        assert request.url.params["include_transformers"] == "true"
        return httpx.Response(200, json={"deleted": {"telemetry": 5, "transformers": 1}})

    monkeypatch.setenv("DEMO_ADMIN_TOKEN", "configured-demo-token")
    factory = httpx.Client
    monkeypatch.setattr(
        reset_script.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert reset_script.run_reset(yes=True, include_transformers=True, base_url="http://demo") == {
        "telemetry": 5,
        "transformers": 1,
    }
