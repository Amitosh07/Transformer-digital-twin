from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.schemas.telemetry import TelemetryInput


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
