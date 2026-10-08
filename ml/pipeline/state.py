"""Per-asset state model for the unified ML/Twin pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from ml.anomaly.detector import AnomalyPersistenceState
from ml.health.engine import HealthPersistenceState
from ml.maintenance.engine import MaintenancePersistenceState
from ml.thermal.thermal_twin import TransformerThermalState


DEFAULT_MAX_HISTORY_ROWS = 60


@dataclass
class AssetPipelineState:
    """Isolated, complete analytical state for a single transformer asset.

    Maintains:
    - Version compatibility metadata (bundle_id, schema_version, feature_version, model_version)
    - Causal rolling history buffer (excluding current uncommitted observation)
    - Phase 01 Thermal Twin persistent state
    - Phase 02 Anomaly persistence state
    - Phase 03 Health Index persistence state
    - Phase 05 Maintenance persistence & trip latch state
    - Last processed timestamp & sequence tracking for idempotency & replay
    - Last analytical result for idempotent returns on duplicate observation
    """

    transformer_id: str
    bundle_id: str
    schema_version: str
    feature_version: str
    model_version: str

    thermal_state: TransformerThermalState = field(init=False)
    anomaly_state: AnomalyPersistenceState = field(init=False)
    health_state: HealthPersistenceState = field(init=False)
    maintenance_state: MaintenancePersistenceState = field(init=False)

    history_records: list[dict[str, Any]] = field(default_factory=list)
    max_history_rows: int = DEFAULT_MAX_HISTORY_ROWS

    last_processed_timestamp: pd.Timestamp | None = None
    last_result: dict[str, Any] | None = None
    observation_count: int = 0

    def __post_init__(self) -> None:
        self.thermal_state = TransformerThermalState(transformer_id=self.transformer_id)
        self.anomaly_state = AnomalyPersistenceState(transformer_id=self.transformer_id)
        self.health_state = HealthPersistenceState(transformer_id=self.transformer_id)
        self.maintenance_state = MaintenancePersistenceState(transformer_id=self.transformer_id)

    def is_compatible(
        self,
        bundle_id: str,
        schema_version: str,
        feature_version: str,
        model_version: str,
    ) -> bool:
        """Check whether this state is compatible with the given bundle/versions."""
        return (
            self.bundle_id == bundle_id
            and self.schema_version == schema_version
            and self.feature_version == feature_version
            and self.model_version == model_version
        )

    def reset(
        self,
        bundle_id: str | None = None,
        schema_version: str | None = None,
        feature_version: str | None = None,
        model_version: str | None = None,
    ) -> None:
        """Reset analytical state upon long gap, version change, or caller instruction."""
        if bundle_id is not None:
            self.bundle_id = bundle_id
        if schema_version is not None:
            self.schema_version = schema_version
        if feature_version is not None:
            self.feature_version = feature_version
        if model_version is not None:
            self.model_version = model_version

        self.thermal_state.reset()
        self.anomaly_state.reset()
        self.health_state.reset()
        self.maintenance_state.reset()

        self.history_records.clear()
        self.last_processed_timestamp = None
        self.last_result = None
        self.observation_count = 0

    def commit_observation(
        self,
        raw_record: dict[str, Any],
        timestamp: pd.Timestamp,
        result: dict[str, Any],
    ) -> None:
        """Commit an accepted observation and resulting analytics to state."""
        self.last_processed_timestamp = timestamp
        self.last_result = result
        self.observation_count += 1

        # Append to rolling history
        self.history_records.append(dict(raw_record))
        if len(self.history_records) > self.max_history_rows:
            self.history_records = self.history_records[-self.max_history_rows :]
