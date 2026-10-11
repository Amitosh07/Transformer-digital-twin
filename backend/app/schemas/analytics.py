"""ML/Twin outputs. Fault predictions concern proxy alarm/trip labels."""

from typing import Literal

from pydantic import ConfigDict, Field, StrictBool, AliasChoices, model_validator
from app.schemas.hackathon import AnalyticsMetadata, RULResult

from app.schemas.common import (
    CanonicalModel,
    FiniteFloat,
    MaintenancePriority,
    ReasonCode,
    UtcDatetime,
)


class HealthComponents(CanonicalModel):
    thermal: FiniteFloat | None = None
    electrical: FiniteFloat | None = None
    loading: FiniteFloat | None = None
    oil: FiniteFloat | None = None
    alarm: FiniteFloat | None = None
    anomaly: FiniteFloat | None = None


class MLResultIn(CanonicalModel):
    metadata: AnalyticsMetadata | None = Field(default=None, validation_alias=AliasChoices('ml_metadata','metadata'))
    rul: RULResult | None = None
    transformer_id: str = Field(min_length=1, max_length=128)
    timestamp: UtcDatetime
    inference_status: Literal["OK", "INSUFFICIENT_DATA"]
    missing_features: list[str] = Field(default_factory=list)
    loading_percent: FiniteFloat | None = None
    thermal_model_temperature: FiniteFloat | None = None
    thermal_residual: FiniteFloat | None = None
    thermal_state: str | None = None
    anomaly_score: FiniteFloat | None = Field(default=None, ge=0, le=1)
    anomaly_flag: StrictBool | None = None
    health_index: FiniteFloat | None = Field(default=None, ge=0, le=100)
    health_components: HealthComponents | None = None
    health_reason_codes: list[ReasonCode] | None = None
    fault_risk: FiniteFloat | None = Field(default=None, ge=0, le=1)
    predicted_fault: str | None = None
    prediction_confidence: FiniteFloat | None = Field(default=None, ge=0, le=1)
    maintenance_priority: MaintenancePriority | None = None
    maintenance_recommendation: str | None = None
    reason_codes: list[ReasonCode] | None = None
    schema_version: str
    feature_version: str
    model_version: str
    error_detail: str | None = None

    @model_validator(mode='after')
    def forecast_release(self):
        f = self.metadata.forecast if self.metadata else None
        if (f and (f.release_status != 'RELEASED' or not f.operational_eligible)) or (self.schema_version == '1.1.0' and f is None):
            if any(v is not None for v in (self.fault_risk,self.predicted_fault,self.prediction_confidence)):
                raise ValueError('operational forecast outputs require release evidence')
        return self


class AnalyticsOut(MLResultIn):
    model_config = ConfigDict(from_attributes=True)
