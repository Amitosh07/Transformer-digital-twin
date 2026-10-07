from typing import Any, Literal

from pydantic import ConfigDict

from app.schemas.common import CanonicalModel, UtcDatetime


class AlertOut(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transformer_id: str
    analytics_id: int | None = None
    telemetry_id: int | None = None
    timestamp: UtcDatetime
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    alert_type: str
    trigger: str
    evidence: dict[str, Any]
    threshold_or_reason: str
    recommended_action: str
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    last_seen_at: UtcDatetime
    created_at: UtcDatetime
    resolved_at: UtcDatetime | None = None
    acknowledged_at: UtcDatetime | None = None
