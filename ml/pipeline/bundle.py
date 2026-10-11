"""Configuration bundle for the unified ML/Twin pipeline."""

from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass, field, asdict
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

RUNTIME_ARTIFACTS = ('thermal_twin_params.json', 'anomaly_detector_params.json',
                     'proxy_prediction_params.json')


class BundleNotReadyError(ValueError):
    """Strict runtime cannot load its declared release; no fallback occurred."""


def load_forecast_artifact(data):
    """Read the real writer's top-level preprocessing, plus legacy nested key."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from ml.prediction.target import MODEL_FEATURE_ALLOWLIST
    pe = data['primary_experiment']
    features = pe['features']
    order = features['order']
    preprocessing = data.get('preprocessing', pe.get('preprocessor'))
    if data.get('preprocessing') and pe.get('preprocessor') and data['preprocessing'] != pe['preprocessor']:
        raise BundleNotReadyError('conflicting preprocessing encodings')
    if order != list(MODEL_FEATURE_ALLOWLIST) or not preprocessing or preprocessing['feature_names'] != order:
        raise BundleNotReadyError('forecast feature ordering incompatible')
    for values in (features['coefficients'], preprocessing['medians'],
                   preprocessing['means'], preprocessing['scales']):
        if set(values) != set(order) or not all(np.isfinite(float(v)) for v in values.values()):
            raise BundleNotReadyError('forecast parameters missing or nonfinite')
    if not np.isfinite(float(features['intercept'])) or any(float(v) <= 0 for v in preprocessing['scales'].values()):
        raise BundleNotReadyError('invalid forecast intercept/scales')
    # The current research release has failed calibration/threshold gates.
    if data['operational_release_status']['is_operationally_released']:
        raise BundleNotReadyError('unsupported operational forecast release')
    model = LogisticRegression()
    model.coef_ = np.array([[features['coefficients'][k] for k in order]], dtype=float)
    model.intercept_ = np.array([features['intercept']], dtype=float)
    model.classes_ = np.array([0., 1.])
    model.n_features_in_ = len(order)
    return ExperimentalProxyPredictor(model=model,
        preprocessor=PreprocessingArtifact.from_dict(preprocessing),
        decision_threshold=0.5, is_operationally_released=False)


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
    runtime_mode: str = 'EXPLICIT_UNVERIFIED_CONFIG'
    configuration_readiness: str = 'UNVERIFIED'
    preprocessing_version: str = '1.0.0'
    artifact_digest: str = 'EXPLICIT_UNVERIFIED_CONFIG'

    @property
    def configuration_fingerprint(self):
        parameters = {name: asdict(getattr(self, name)) for name in (
            'thermal_config', 'anomaly_config', 'health_config', 'maintenance_config')}
        if self.forecast_model is not None:
            parameters['forecast'] = {
                'preprocessing': self.forecast_model.preprocessor.to_dict(),
                'coefficients': self.forecast_model.model.coef_.tolist(),
                'intercept': self.forecast_model.model.intercept_.tolist(),
                'threshold': self.forecast_model.decision_threshold,
                'released': self.forecast_model.is_operationally_released}
        return hashlib.sha256(json.dumps(parameters, sort_keys=True, allow_nan=False,
            default=lambda value: value.value).encode('utf-8')).hexdigest()

    @classmethod
    def load_from_processed_dir(cls, processed_dir: Path | str | None = None,
                                *, mode: str | None = None) -> PipelineBundle:
        """Strict fitted release by default; demo requires an explicit opt-in."""
        mode = mode or os.environ.get('ML_RUNTIME_MODE', 'STRICT_FITTED')
        if mode == 'DEMO_UNVERIFIED_CONFIG':
            return cls(bundle_id='demo_unverified_coded_config_v1',
                       model_version='DEMO_UNVERIFIED_CONFIG', runtime_mode=mode,
                       configuration_readiness='UNVERIFIED')
        if mode != 'STRICT_FITTED':
            raise BundleNotReadyError(f'unknown runtime mode: {mode}')
        processed_dir = Path(processed_dir or os.environ.get('ML_ARTIFACT_DIR') or
                             Path(__file__).resolve().parents[2] / 'data' / 'processed')
        try:
            manifest = json.loads((processed_dir / 'release_manifest.json').read_text(encoding='utf-8'))
            versions = manifest['versions']
            if manifest['manifest_version'] != '1.0.0':
                raise BundleNotReadyError('incompatible manifest schema')
            if any(versions[k] != '1.0.0' for k in ('schema_version', 'feature_version',
                    'preprocessing_version', 'model_version', 'thermal_parameter_version',
                    'anomaly_detector_version', 'prediction_model_version', 'bundle_version')):
                raise BundleNotReadyError('incompatible release versions')
            declared = manifest['provenance_hashes']['processed_artifacts']
            data = {}
            for name in RUNTIME_ARTIFACTS:
                content = (processed_dir / name).read_bytes()
                if hashlib.sha256(content).hexdigest() != declared[name]:
                    raise BundleNotReadyError(f'artifact hash mismatch: {name}')
                data[name] = json.loads(content)
            thermal = data['thermal_twin_params.json']
            p = thermal['parameters']
            thermal_cfg = ThermalTwinConfig(b0=float(p['b0']), bA=float(p['bA']),
                bJ=float(p['bJ']), tau_hours=float(p['tau_hours']),
                mode=ThermalModelMode(thermal['mode']), temperature_unit=thermal['temperature_unit'],
                continuity_gap_hours=float(p.get('continuity_gap_hours', 0.5)),
                parameter_version=thermal['parameter_version'])
            anomaly = data[RUNTIME_ARTIFACTS[1]]
            persistence = anomaly['persistence_config']
            if anomaly['detector_version'] != versions['anomaly_detector_version'] or not anomaly['thresholds']:
                raise BundleNotReadyError('anomaly artifact incompatible')
            anomaly_cfg = AnomalyDetectorConfig.from_dict({
                'thresholds': anomaly['thresholds'], 'a_on': anomaly['selected_a_on'],
                'detector_version': anomaly['detector_version'],
                'min_persistence_observations': persistence['min_observations'],
                'min_persistence_span_hours': persistence['min_span_hours'],
                'continuity_gap_hours': persistence['continuity_gap_hours'],
                'min_current_gate_a': persistence['min_current_gate_a']})
            forecast = load_forecast_artifact(data[RUNTIME_ARTIFACTS[2]])
            if manifest['subsystem_metadata']['proxy_prediction']['feature_order'] != data[RUNTIME_ARTIFACTS[2]]['primary_experiment']['features']['order']:
                raise BundleNotReadyError('manifest/artifact feature ordering mismatch')
            if thermal['parameter_version'] != versions['thermal_parameter_version'] or data[RUNTIME_ARTIFACTS[2]]['model_version'] != versions['prediction_model_version']:
                raise BundleNotReadyError('artifact/manifest version mismatch')
            digest = hashlib.sha256((processed_dir / 'release_manifest.json').read_bytes()).hexdigest()
            return cls(bundle_id='processed_bundle_v1', thermal_config=thermal_cfg,
                       anomaly_config=anomaly_cfg, forecast_model=forecast,
                       runtime_mode=mode, configuration_readiness='HASH_VERIFIED_SOURCE_UNITS_UNVERIFIED',
                       artifact_digest=digest)
        except BundleNotReadyError:
            raise
        except Exception as exc:
            raise BundleNotReadyError(f'strict fitted release not ready: {exc}') from exc
