from typing import Literal

from pydantic import ConfigDict

from app.schemas.common import CanonicalModel, MaintenancePriority, ReasonCode, UtcDatetime


class MaintenanceOut(CanonicalModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transformer_id: str
    analytics_id: int | None = None
    timestamp: UtcDatetime
    priority: MaintenancePriority
    recommendation: str
    reason_codes: list[ReasonCode]
    status: Literal["OPEN", "DONE", "DISMISSED"]
    created_at: UtcDatetime
