"""Read-only MQTT diagnostics."""

from typing import Any

from fastapi import APIRouter, Request

from app.schemas.mqtt import MqttStatus
from app.services.mqtt_status_service import mqtt_status

router = APIRouter(tags=["ingestion"])
EXAMPLE = MqttStatus(
    enabled=True,
    host="localhost",
    port=1883,
    topic="transformer/+/telemetry",
    qos=1,
    last_message_at="2026-10-07T09:00:00Z",
    last_error="BROKER_UNREACHABLE",
).model_dump(mode="json")


@router.get(
    "/ingest/mqtt/status",
    response_model=MqttStatus,
    description=(
        "An enabled consumer with an unavailable broker reports connected=false (HTTP 200)."
    ),
    responses={200: {"content": {"application/json": {"example": EXAMPLE}}}},
)
def get_mqtt_status(request: Request) -> dict[str, Any]:
    return mqtt_status(getattr(request.app.state, "mqtt_consumer", None))
