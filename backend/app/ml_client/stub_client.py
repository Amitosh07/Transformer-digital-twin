"""Deterministic demonstration adapter; alarm/trip outputs are proxy predictions."""

from app.core.config import Settings, get_settings
from app.ml_client.base import MLClientError, validate_history
from app.schemas.analytics import HealthComponents, MLResultIn
from app.schemas.common import MaintenancePriority, ReasonCode
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


class StubMLTwinClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else get_settings()

    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        validate_history(transformer, record, history, self.settings.ml_history_window)
        result = MLResultIn(
            transformer_id=record.transformer_id,
            timestamp=record.timestamp,
            inference_status="INSUFFICIENT_DATA",
            schema_version=self.settings.schema_version,
            feature_version="1.0.0",
            model_version="stub-0.0.0",
            missing_features=[
                field
                for field in ("oil_temperature", "oil_level")
                if getattr(record, field) is None
            ],
        )
        if result.missing_features:
            return result

        priority: MaintenancePriority
        reasons: list[ReasonCode]
        if record.oil_temp_trip == 1:
            priority, reasons = "URGENT", ["OIL_TEMP_TRIP"]
            anomaly_score, anomaly_flag, health, risk = 0.95, True, 25.0, 0.9
        elif record.oil_temp_alarm == 1:
            priority, reasons = "PLAN", ["OIL_TEMP_ALARM", "HIGH_OIL_TEMP"]
            anomaly_score, anomaly_flag, health, risk = 0.75, True, 55.0, 0.6
        elif record.magnetic_oil_gauge_alarm == 1:
            priority, reasons = "PLAN", ["MOG_ALARM"]
            anomaly_score, anomaly_flag, health, risk = 0.5, True, 60.0, 0.3
        else:
            priority, reasons = "NORMAL", []
            anomaly_score, anomaly_flag, health, risk = 0.1, False, 90.0, 0.05

        loading = None
        if transformer.rated_power_kva is not None and record.apparent_power_total is not None:
            if transformer.rated_power_kva <= 0:
                raise MLClientError("Rated power must be positive to calculate loading_percent")
            loading = record.apparent_power_total / transformer.rated_power_kva * 100

        recommendations = {
            "NORMAL": "Continue routine monitoring.",
            "PLAN": "Plan an inspection of the indicated protection condition.",
            "URGENT": "Arrange urgent inspection of the trip indication; follow site procedures.",
        }
        result.inference_status = "OK"
        result.loading_percent = loading
        result.anomaly_score = anomaly_score
        result.anomaly_flag = anomaly_flag
        result.health_index = health
        result.fault_risk = risk
        result.predicted_fault = "THERMAL_STRESS" if risk >= 0.5 else None
        result.prediction_confidence = 0.8 if risk >= 0.5 else None
        result.maintenance_priority = priority
        result.maintenance_recommendation = recommendations[priority]
        result.reason_codes = reasons
        result.health_reason_codes = list(reasons)
        result.health_components = HealthComponents(
            thermal=health,
            electrical=90.0,
            loading=90.0,
            oil=60.0 if record.magnetic_oil_gauge_alarm == 1 else 90.0,
            alarm=health,
            anomaly=(1 - anomaly_score) * 100,
        )
        # Validate arithmetic results as well as constants, including overflow.
        return MLResultIn.model_validate(result.model_dump(mode="python"))
