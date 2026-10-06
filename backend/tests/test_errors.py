import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.schemas.common import ErrorResponse
from app.schemas.telemetry import TelemetryIn, TelemetryInput


def test_error_envelopes() -> None:
    application = FastAPI()
    register_exception_handlers(application)

    @application.post("/validate")
    def validate(record: TelemetryInput) -> dict[str, str]:
        return {"transformer_id": record.transformer_id}

    @application.get("/failure")
    def failure() -> None:
        raise RuntimeError("private database details")

    @application.get("/denied")
    def denied() -> None:
        raise HTTPException(401, "Denied", headers={"WWW-Authenticate": "Bearer"})

    with TestClient(application, raise_server_exceptions=False) as client:
        for path, expected in [("/missing", 404), ("/failure", 500), ("/denied", 401)]:
            response = client.get(path)
            assert response.status_code == expected
            assert set(response.json()["error"]) == {"code", "message", "details"}
            assert "private" not in response.text
        assert client.get("/denied").headers["WWW-Authenticate"] == "Bearer"
        for body in [
            {"transformer_id": "TX-001", "timestamp": "2026-10-06T00:00:00Z", "VL12": 1},
            {"transformer_id": "TX-001", "timestamp": "2026-10-06T00:00:00"},
        ]:
            response = client.post("/validate", json=body)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("field", ["VL12", "vl23", "VL31", "VL_12", "vl_23", "VL_31", "unknown"])
def test_validation_error_details_and_excluded_messages(field: str) -> None:
    # Test-only routes exercise the shared handler without adding production endpoints.
    application = FastAPI()
    register_exception_handlers(application)

    @application.post("/validate")
    def validate(record: TelemetryIn) -> dict[str, str]:
        return {"transformer_id": record.transformer_id}

    with TestClient(application) as client:
        response = client.post(
            "/validate",
            json={"transformer_id": "TX-001", "timestamp": "2026-10-06T00:00:00Z", field: 1},
        )
    assert response.status_code == 422
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == "VALIDATION_ERROR"
    assert isinstance(error.details, list)
    assert error.details
    if field == "unknown":
        assert error.details[0]["type"] == "extra_forbidden"
    else:
        assert "excluded from the canonical schema" in error.details[0]["message"]
    assert "traceback" not in response.text.lower()
