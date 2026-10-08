"""Configuration bundle for the unified ML/Twin pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ml.anomaly.detector import AnomalyDetectorConfig, get_default_training_thresholds
from ml.health.engine import HealthIndexConfig
from ml.maintenance.engine import MaintenanceEngineConfig
from ml.prediction.model import (
    ExperimentalProxyPredictor,
    PreprocessingArtifact,
    STATUS_INSUFFICIENT_VALIDATION,
)
from ml.thermal.thermal_twin import ThermalModelMode, ThermalTwinConfig


SCHEMA_VERSION = "1.0.0"
FEATURE_VERSION = "1.0.0"
MODEL_VERSION = "1.0.0"


@dataclass(frozen=True)
class PipelineBundle:
    """Versioned configuration and model parameters for all pipeline components.

    Ensures explicit version tracking and compatibility validation.
    """

    bundle_id: str = "default_v1"
    schema_version: str = SCHEMA_VERSION
    feature_version: str = FEATURE_VERSION
    model_version: str = MODEL_VERSION
    thermal_config: ThermalTwinConfig = field(default_factory=ThermalTwinConfig)
    anomaly_config: AnomalyDetectorConfig = field(
        default_factory=lambda: AnomalyDetectorConfig(
            thresholds=get_default_training_thresholds(),
            a_on=0.5,
        )
    )
    health_config: HealthIndexConfig = field(default_factory=HealthIndexConfig)
    maintenance_config: MaintenanceEngineConfig = field(default_factory=MaintenanceEngineConfig)
    forecast_model: ExperimentalProxyPredictor | None = None
    forecast_operational_status: str = STATUS_INSUFFICIENT_VALIDATION

    @classmethod
    def load_from_processed_dir(cls, processed_dir: Path | str | None = None) -> PipelineBundle:
        """Load fitted parameters if available in data/processed, otherwise defaults."""
        if processed_dir is None:
            processed_dir = Path(__file__).resolve().parents[2] / "data" / "processed"
        else:
            processed_dir = Path(processed_dir)

        # 1. Thermal twin
        thermal_cfg = ThermalTwinConfig()
        thermal_file = processed_dir / "thermal_twin_params.json"
        if thermal_file.exists():
            try:
                with open(thermal_file, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                p = t_data.get("parameters", {})
                thermal_cfg = ThermalTwinConfig(
                    b0=float(p.get("b0", thermal_cfg.b0)),
                    bA=float(p.get("bA", thermal_cfg.bA)),
                    bJ=float(p.get("bJ", thermal_cfg.bJ)),
                    tau_hours=float(p.get("tau_hours", thermal_cfg.tau_hours)),
                    mode=ThermalModelMode(t_data.get("mode", ThermalModelMode.PUBLIC_EMPIRICAL.value)),
                    temperature_unit=str(t_data.get("temperature_unit", "SOURCE_UNVERIFIED")),
                    continuity_gap_hours=float(p.get("continuity_gap_hours", 0.5)),
                    parameter_version=str(t_data.get("parameter_version", "1.0.0")),
                )
            except Exception:
                pass

        # 2. Anomaly detector
        anomaly_cfg = AnomalyDetectorConfig(
            thresholds=get_default_training_thresholds(),
            a_on=0.5,
        )
        anomaly_file = processed_dir / "anomaly_detector_params.json"
        if anomaly_file.exists():
            try:
                anomaly_cfg = AnomalyDetectorConfig.from_json_file(anomaly_file)
            except Exception:
                pass

        # 3. Health & Maintenance
        health_cfg = HealthIndexConfig()
        maint_cfg = MaintenanceEngineConfig()

        # 4. Forecast predictor
        forecast_predictor: LogisticRegressionProxyPredictor | None = None
        forecast_status = STATUS_INSUFFICIENT_VALIDATION
        forecast_file = processed_dir / "proxy_prediction_params.json"
        if forecast_file.exists():
            try:
                with open(forecast_file, "r", encoding="utf-8") as f:
                    f_data = json.load(f)
                op_status = f_data.get("operational_release_status", {})
                forecast_status = op_status.get("default_inference_status", STATUS_INSUFFICIENT_VALIDATION)
                # Build predictor from primary experiment coefficients if present
                pe = f_data.get("primary_experiment", {})
                ft = pe.get("features", {})
                feat_order = ft.get("order", [])
                coeffs = ft.get("coefficients", {})
                intercept = float(ft.get("intercept", 0.0))
                preproc_dict = pe.get("preprocessor", {})
                if feat_order and preproc_dict and coeffs:
                    from sklearn.linear_model import LogisticRegression
                    import numpy as np
                    lr = LogisticRegression()
                    lr.coef_ = np.array([[coeffs[col] for col in feat_order]], dtype=float)
                    lr.intercept_ = np.array([intercept], dtype=float)
                    lr.classes_ = np.array([0.0, 1.0])
                    preproc = PreprocessingArtifact.from_dict(preproc_dict)
                    forecast_predictor = ExperimentalProxyPredictor(
                        model=lr,
                        preprocessor=preproc,
                        decision_threshold=0.5,
                        is_operationally_released=bool(op_status.get("is_operationally_released", False)),
                    )
            except Exception:
                pass

        return cls(
            bundle_id="processed_bundle_v1",
            schema_version=SCHEMA_VERSION,
            feature_version=FEATURE_VERSION,
            model_version=MODEL_VERSION,
            thermal_config=thermal_cfg,
            anomaly_config=anomaly_cfg,
            health_config=health_cfg,
            maintenance_config=maint_cfg,
            forecast_model=forecast_predictor,
            forecast_operational_status=forecast_status,
        )
