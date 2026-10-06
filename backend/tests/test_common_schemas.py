import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.schemas.common import ErrorResponse, Page
from app.schemas.telemetry import TelemetryIn


def test_typed_page_and_bounds() -> None:
    payload = {"transformer_id": "TX-001", "timestamp": "2026-10-06T00:00:00Z"}
    page = Page[TelemetryIn](items=[payload], total=1, limit=10, offset=0)
    assert isinstance(page.items[0], TelemetryIn)
    assert page.model_dump(mode="json")["items"][0]["transformer_id"] == "TX-001"
    for field, value in [("total", -1), ("limit", 0), ("offset", -1)]:
        with pytest.raises(ValidationError):
            Page[TelemetryIn](
                **({"items": [], "total": 0, "limit": 10, "offset": 0} | {field: value})
            )


def test_shared_errors_match_schema() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/not-found")
    parsed = ErrorResponse.model_validate(response.json())
    assert parsed.error.code == "HTTP_ERROR"
    assert response.status_code == 404
    assert set(parsed.error.model_dump()) == {"code", "message", "details"}
