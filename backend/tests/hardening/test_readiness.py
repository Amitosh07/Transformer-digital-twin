from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ml_client.http_client import HttpMLTwinClient
from app.ml_client.python_client import PythonMLTwinClient
from app.repositories import readiness_repo
from app.services import readiness_service


def test_ready_and_unchanged_health(hard_client: TestClient) -> None:
    response = hard_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "db": "ready",
        "migrations": "ready",
        "ml": "ready",
        "details": {},
    }
    assert hard_client.get("/health").json() == {
        "status": "ok",
        "db": "ok",
        "schema_version": "1.0.0",
    }


def test_revision_mismatch(hard_client: TestClient, db: Session) -> None:
    db.execute(text("UPDATE alembic_version SET version_num='old-revision'"))
    response = hard_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["db"] == "ready" and response.json()["migrations"] == "error"


def test_db_failure_is_sanitized(hard_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: Any) -> None:
        raise SQLAlchemyError("private database details")

    monkeypatch.setattr(readiness_repo, "check", broken)
    response = hard_client.get("/health/ready")
    assert response.status_code == 503 and response.json()["db"] == "error"
    assert "private" not in response.text


def test_not_ready_outside_lifespan_and_during_startup(db: Session) -> None:
    from app.db.session import get_db
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        app.state.started = False
        assert client.get("/health/ready").status_code == 503
        app.state.started = True
        assert client.get("/health/ready").status_code == 200
    assert app.state.started is False
    assert TestClient(app).get("/health/ready").status_code == 503


@pytest.mark.parametrize(
    "codes,expected",
    [
        ([200], "ready"),
        ([405, 200], "ready"),
        ([405, 501], "unchecked"),
        ([503], "error"),
        ([401], "error"),
        ([302], "error"),
    ],
)
def test_http_probe_bounded_and_non_inferential(
    db: Session, monkeypatch: pytest.MonkeyPatch, codes: list[int], expected: str
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method in ("HEAD", "GET") and not request.content
        assert request.extensions["timeout"]["read"] <= 1
        return httpx.Response(codes[len(requests) - 1])

    settings = Settings(_env_file=None, ml_backend="http", ml_http_url="https://ml.example/analyze")
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        adapter = HttpMLTwinClient(settings, http_client=transport)
        monkeypatch.setattr(readiness_service, "get_ml_client", lambda: adapter)
        result = readiness_service.check_ready(db, settings, True)
    assert result.ml == expected
    assert (result.status == "ready") == (expected in ("ready", "unchecked"))
    assert len(requests) == len(codes)


def test_http_timeout_reports_not_ready(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private network details")

    settings = Settings(_env_file=None, ml_backend="http", ml_http_url="https://ml.example/analyze")
    with httpx.Client(transport=httpx.MockTransport(timeout)) as transport:
        adapter = HttpMLTwinClient(settings, http_client=transport)
        monkeypatch.setattr(readiness_service, "get_ml_client", lambda: adapter)
        result = readiness_service.check_ready(db, settings, True)
    assert result.status == "not_ready" and result.ml == "error"
    assert "private" not in result.model_dump_json()


@pytest.mark.parametrize(
    "entrypoint,expected",
    [
        ("builtins:abs", "error"),  # Importability alone is not a transactional runtime.
        ("missing_phase8_module:predict", "error"),
        ("builtins:missing", "error"),
        ("invalid", "error"),
        ("builtins:None", "error"),
    ],
)
def test_python_importability(
    db: Session, monkeypatch: pytest.MonkeyPatch, entrypoint: str, expected: str
) -> None:
    settings = Settings(_env_file=None, ml_backend="python", ml_python_entrypoint=entrypoint)
    adapter = PythonMLTwinClient(settings)
    monkeypatch.setattr(readiness_service, "get_ml_client", lambda: adapter)
    result = readiness_service.check_ready(db, settings, True)
    assert result.ml == expected
    assert (result.status == "ready") == (expected == "ready")


def test_client_construction_failure_and_mismatch(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(_env_file=None, ml_backend="http")

    def fail() -> None:
        raise ValueError("private config")

    monkeypatch.setattr(readiness_service, "get_ml_client", fail)
    assert readiness_service.check_ready(db, settings, True).ml == "error"
    monkeypatch.setattr(readiness_service, "get_ml_client", lambda: object())
    assert readiness_service.check_ready(db, settings, True).ml == "error"


def test_http_probe_checks_headers_without_downloading_bodies() -> None:
    class UnreadableBody(httpx.SyncByteStream):
        def __iter__(self) -> Any:
            raise AssertionError("Readiness must not download a response body")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(405 if request.method == "HEAD" else 200, stream=UnreadableBody())

    settings = Settings(_env_file=None, ml_backend="http", ml_http_url="https://ml.example/analyze")
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        assert HttpMLTwinClient(settings, http_client=transport).probe() == "ready"


def test_stub_is_ready_even_while_startup_is_pending(db: Session) -> None:
    result = readiness_service.check_ready(db, Settings(_env_file=None), False)
    assert result.status == "not_ready" and result.ml == "ready"
