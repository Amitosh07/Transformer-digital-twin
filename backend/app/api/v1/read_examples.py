"""Concrete OpenAPI examples with canonical values and proxy-risk wording."""

from typing import Any

from app.schemas.analytics import AnalyticsOut
from app.schemas.common import ErrorResponse
from app.schemas.query import AnalyticsPoint, HealthPoint, TelemetryPoint
from app.schemas.state import LatestStateOut
from app.schemas.telemetry import TelemetryOut
from app.schemas.transformer import TransformerOut

TIME = "2026-10-07T09:00:00Z"
TRANSFORMER = TransformerOut(
    id="TX-001", name="Demo transformer", created_at=TIME, updated_at=TIME
).model_dump(mode="json")
TELEMETRY = TelemetryOut(
    transformer_id="TX-001",
    timestamp=TIME,
    id=1,
    oil_temperature=42,
    oil_level=8,
    source_name="simulator",
    scenario_id="normal-demo",
    is_missing_critical=True,
    data_quality_score=2 / 21,
    schema_version="1.0.0",
).model_dump(mode="json")
ANALYTICS = AnalyticsOut(
    transformer_id="TX-001",
    timestamp=TIME,
    inference_status="OK",
    anomaly_score=0.1,
    health_index=90,
    fault_risk=0.05,
    schema_version="1.0.0",
    feature_version="1.0.0",
    model_version="stub-0.0.0",
).model_dump(mode="json")
LATEST = LatestStateOut(
    transformer=TRANSFORMER,
    telemetry=TELEMETRY,
    analytics=ANALYTICS,
    open_alerts_count=0,
    demo_mode=True,
    data_source={"source_name": "simulator", "scenario_id": "normal-demo"},
    schema_version="1.0.0",
    feature_version="1.0.0",
    model_version="stub-0.0.0",
).model_dump(mode="json")
HEALTH = HealthPoint(**{name: ANALYTICS[name] for name in HealthPoint.model_fields}).model_dump(
    mode="json"
)
ANALYTIC_POINT = AnalyticsPoint(
    **{name: ANALYTICS[name] for name in AnalyticsPoint.model_fields}
).model_dump(mode="json")
TELEMETRY_POINT = TelemetryPoint(**TELEMETRY).model_dump(mode="json")
ALERT = {
    "id": 1,
    "transformer_id": "TX-001",
    "timestamp": TIME,
    "severity": "WARNING",
    "alert_type": "PROTECTION",
    "trigger": "oil_temp_alarm",
    "evidence": {"oil_temp_alarm": 1},
    "threshold_or_reason": "OIL_TEMP_ALARM",
    "recommended_action": "Inspect indication",
    "status": "OPEN",
    "last_seen_at": TIME,
    "created_at": TIME,
}
MAINTENANCE = {
    "id": 1,
    "transformer_id": "TX-001",
    "timestamp": TIME,
    "priority": "PLAN",
    "recommendation": "Inspect the proxy alarm indication",
    "reason_codes": ["OIL_TEMP_ALARM"],
    "status": "OPEN",
    "created_at": TIME,
}
TREND = {
    "start": "2026-10-07T08:00:00Z",
    "end": TIME,
    "bucket_seconds": 15,
    "signals": {
        "oil_temperature": [
            {"bucket_start": "2026-10-07T08:00:00Z", "avg": 42, "min": 42, "max": 42, "count": 1}
        ]
    },
    "no_data_signals": [],
    "protection_events": [],
}
SCENARIO = {
    "scenario_id": "normal-demo",
    "first_timestamp": TIME,
    "last_timestamp": TIME,
    "row_count": 1,
}


def page_example(item: dict[str, Any]) -> dict[str, Any]:
    return {"items": [item], "total": 1, "limit": 500, "offset": 0}


def response_example(value: dict[str, Any], status: int = 200) -> dict[int, Any]:
    responses = {
        status: {"content": {"application/json": {"example": value}}},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        404: {"model": ErrorResponse, "description": "Transformer not found"},
    }
    if status == 201:
        responses[409] = {"model": ErrorResponse, "description": "Transformer already exists"}
    return responses
