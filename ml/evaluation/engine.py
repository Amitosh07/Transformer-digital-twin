"""Master evaluation harness and report generation for Phase 06.

Phase 06 — Time-Aware Evaluation:
- Orchestrates reproducible, time-aware evaluation across:
    1. Thermal Twin & 3 baselines
    2. Anomaly detection & false-alert burden
    3. Forecast proxy prediction (Primary & Exploratory)
    4. Health Index 8 mandatory fixtures
    5. Maintenance Engine 11 mandatory scenarios
    6. 5-point operational release gate
- Outputs structured evaluation report JSON with formal capability statuses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ml.evaluation.anomaly_eval import evaluate_anomaly_on_partition
from ml.evaluation.fixtures_eval import (
    verify_health_index_fixtures,
    verify_maintenance_scenarios,
)
from ml.evaluation.forecast_eval import (
    evaluate_forecast_binary_partition,
    evaluate_operational_release_gate,
)
from ml.evaluation.splits import (
    DEFAULT_HORIZON_HOURS,
    DEFAULT_MAX_GAP_HOURS,
    SPLIT_TRAIN_END,
    SPLIT_VAL_END,
    compute_adequately_observed_asset_days,
    compute_file_sha256,
    partition_primary_chronological_splits,
)
from ml.evaluation.thermal_eval import (
    evaluate_thermal_twin_and_baselines,
    fit_ambient_dynamic_baseline,
    fit_ambient_offset_baseline,
)
from ml.prediction.model import (
    fit_train_preprocessing,
    run_exploratory_event_era_experiment,
)
from ml.prediction.target import (
    TARGET_HORIZON_HOURS,
    TARGET_NAME,
    TARGET_VERSION,
    build_proxy_target_table,
    compute_three_valued_contact_state,
    extract_model_features,
    find_valid_onsets,
)
from ml.thermal.calibration import (
    extract_clean_training_runs,
    fit_thermal_twin_parameters,
    generate_chronological_oof_residuals,
)
from ml.thermal.thermal_twin import ThermalTwinConfig

DEFAULT_REPORT_OUTPUT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "evaluation_report.json"
)


class EvaluationHarness:
    """Master harness executing time-aware evaluation for Transformer Digital Twin."""

    def __init__(
        self,
        canonical_df: pd.DataFrame,
        features_df: pd.DataFrame | None = None,
        thermal_residuals_oof: pd.Series | None = None,
        data_source_path: Path | str | None = None,
    ) -> None:
        self.canonical_df = canonical_df.copy()
        if not pd.api.types.is_datetime64_any_dtype(self.canonical_df.get("timestamp")):
            self.canonical_df["timestamp"] = pd.to_datetime(self.canonical_df.get("timestamp"))
        self.features_df = features_df
        self.thermal_residuals_oof = thermal_residuals_oof
        self.data_source_path = data_source_path

    def run_all(self) -> dict[str, Any]:
        """Execute full suite of time-aware evaluations and return structured report."""
        # 1. Dataset & Provenance
        file_hash = (
            compute_file_sha256(self.data_source_path)
            if self.data_source_path
            else "MEMORY_DATAFRAME"
        )
        total_rows = len(self.canonical_df)
        ts = pd.to_datetime(self.canonical_df["timestamp"])
        t_min = str(ts.min()) if not ts.empty else None
        t_max = str(ts.max()) if not ts.empty else None

        # 2. Partition primary chronological splits
        splits = partition_primary_chronological_splits(self.canonical_df)
        train_df = splits["train"]
        val_df = splits["val"]
        test_df = splits["test"]
        train_purged_df = splits["train_purged"]
        val_purged_df = splits["val_purged"]

        split_accounting = {
            "train": {
                "total_rows": len(train_df),
                "purged_rows": len(train_purged_df),
                "purge_rationale": "1-hour target horizon purge applied before train split boundary",
                "observed_asset_days": compute_adequately_observed_asset_days(train_df["timestamp"]),
                "start_timestamp": str(train_df["timestamp"].min()) if not train_df.empty else None,
                "end_timestamp": str(train_df["timestamp"].max()) if not train_df.empty else None,
            },
            "validation": {
                "total_rows": len(val_df),
                "purged_rows": len(val_purged_df),
                "purge_rationale": "1-hour target horizon purge applied before validation split boundary",
                "observed_asset_days": compute_adequately_observed_asset_days(val_df["timestamp"]),
                "start_timestamp": str(val_df["timestamp"].min()) if not val_df.empty else None,
                "end_timestamp": str(val_df["timestamp"].max()) if not val_df.empty else None,
            },
            "test": {
                "total_rows": len(test_df),
                "purged_rows": 0,
                "observed_asset_days": compute_adequately_observed_asset_days(test_df["timestamp"]),
                "start_timestamp": str(test_df["timestamp"].min()) if not test_df.empty else None,
                "end_timestamp": str(test_df["timestamp"].max()) if not test_df.empty else None,
            },
        }

        # 3. Thermal Twin & Baselines Evaluation
        clean_runs = extract_clean_training_runs(train_df)
        twin_config, _ = fit_thermal_twin_parameters(clean_runs)
        ambient_offset = fit_ambient_offset_baseline(train_df)
        amb_dynamic_config = fit_ambient_dynamic_baseline(train_df)

        thermal_train = evaluate_thermal_twin_and_baselines(
            train_df, twin_config, ambient_offset, amb_dynamic_config
        )
        thermal_val = evaluate_thermal_twin_and_baselines(
            val_df, twin_config, ambient_offset, amb_dynamic_config
        )
        thermal_test = evaluate_thermal_twin_and_baselines(
            test_df, twin_config, ambient_offset, amb_dynamic_config
        )

        thermal_evaluation = {
            "model_version": "1.0.0",
            "parameters": {
                "b0": twin_config.b0,
                "bA": twin_config.bA,
                "bJ": twin_config.bJ,
                "tau_hours": twin_config.tau_hours,
            },
            "baselines_evaluated": [
                "prior_oil_observation_persistence",
                "ambient_median_offset",
                "ambient_only_dynamic_first_order",
            ],
            "train": thermal_train,
            "validation": thermal_val,
            "test": thermal_test,
        }

        # 4. Anomaly Detection & False Alert Evaluation
        from ml.anomaly.detector import AnomalyDetector, AnomalyDetectorConfig, run_anomaly_detection

        # Run anomaly detector on partitions
        det = AnomalyDetector()
        val_anomaly_df = det.run(val_df)
        test_anomaly_df = det.run(test_df)

        anomaly_val = evaluate_anomaly_on_partition(val_anomaly_df)
        anomaly_test = evaluate_anomaly_on_partition(test_anomaly_df)

        anomaly_evaluation = {
            "detector_version": "1.0.0",
            "validation": anomaly_val,
            "test": anomaly_test,
            "evaluation_note": "Validation and test partitions contain zero verified trip ground truth; flagged episodes represent empirical operational alert burden.",
        }

        # 5. Forecast / Phase 04 Proxy Evaluation
        target_table = build_proxy_target_table(self.canonical_df)
        b_state = compute_three_valued_contact_state(
            self.canonical_df["oil_temp_alarm"],
            self.canonical_df["oil_temp_trip"],
        )
        all_onsets = find_valid_onsets(ts, b_state)
        onsets_map = {o["event_id"]: pd.Timestamp(o["timestamp"]) for o in all_onsets}

        # If features or residuals not provided, compute them
        if self.features_df is None:
            from ml.features.feature_engineering import build_features
            self.features_df = build_features(self.canonical_df)

        if self.thermal_residuals_oof is None:
            self.thermal_residuals_oof = generate_chronological_oof_residuals(
                self.canonical_df, twin_config
            )

        X_raw = extract_model_features(
            self.features_df,
            thermal_residuals=self.thermal_residuals_oof,
            allow_superset=True,
        )

        # Primary splits masks for target
        h = pd.Timedelta(hours=TARGET_HORIZON_HOURS)
        t_train_end = pd.Timestamp(SPLIT_TRAIN_END)
        t_val_end = pd.Timestamp(SPLIT_VAL_END)

        train_mask = (ts < t_train_end - h) & target_table["is_eligible"]
        val_mask = (ts >= t_train_end) & (ts < t_val_end - h) & target_table["is_eligible"]
        test_mask = (ts >= t_val_end) & target_table["is_eligible"]

        train_y = target_table.loc[train_mask, "target_y"].dropna()
        val_y = target_table.loc[val_mask, "target_y"].dropna()
        test_y = target_table.loc[test_mask, "target_y"].dropna()

        train_idx = train_y.index
        val_idx = val_y.index
        test_idx = test_y.index

        preprocessor = fit_train_preprocessing(X_raw.loc[train_idx])
        X_train = preprocessor.transform(X_raw.loc[train_idx])
        X_val = preprocessor.transform(X_raw.loc[val_idx])
        X_test = preprocessor.transform(X_raw.loc[test_idx])

        from sklearn.linear_model import LogisticRegression
        from ml.prediction.model import compute_event_balanced_sample_weights

        events_train = target_table.loc[train_idx, "associated_event_id"]
        sample_weights = compute_event_balanced_sample_weights(train_y, events_train)

        clf = LogisticRegression(C=1.0, random_state=42)
        clf.fit(X_train, train_y.to_numpy(), sample_weight=sample_weights)

        val_probs = clf.predict_proba(X_val)[:, 1]
        test_probs = clf.predict_proba(X_test)[:, 1]
        train_prior = float(train_y.mean())

        forecast_val = evaluate_forecast_binary_partition(
            val_y,
            val_probs,
            timestamps=target_table.loc[val_idx, "timestamp"],
            associated_event_ids=target_table.loc[val_idx, "associated_event_id"],
            onsets_map=onsets_map,
            threshold=0.5,
            train_prior=train_prior,
        )
        forecast_test = evaluate_forecast_binary_partition(
            test_y,
            test_probs,
            timestamps=target_table.loc[test_idx, "timestamp"],
            associated_event_ids=target_table.loc[test_idx, "associated_event_id"],
            onsets_map=onsets_map,
            threshold=0.5,
            train_prior=train_prior,
        )

        # Release gate evaluation
        release_gate = evaluate_operational_release_gate(forecast_val, forecast_test)

        # Exploratory event-era experiment
        exploratory_res = run_exploratory_event_era_experiment(
            canonical_df=self.canonical_df,
            features_df=self.features_df,
            thermal_residuals_oof=self.thermal_residuals_oof,
            target_table=target_table,
            onsets_map=onsets_map,
        )

        forecast_evaluation = {
            "target_name": TARGET_NAME,
            "target_version": TARGET_VERSION,
            "horizon_hours": TARGET_HORIZON_HOURS,
            "primary_experiment": {
                "validation": forecast_val,
                "test": forecast_test,
                "release_gate": release_gate,
            },
            "exploratory_experiment": exploratory_res,
        }

        # 6. Health Index Fixtures Verification
        hi_fixtures = verify_health_index_fixtures()

        # 7. Maintenance Scenarios Verification
        maint_scenarios = verify_maintenance_scenarios()

        # 8. Formal Capability Status Breakdown
        capability_statuses = {
            "prerequisite_remediation_phase00": "IMPLEMENTED_AND_EVALUATED",
            "thermal_twin_phase01": "IMPLEMENTED_AND_EVALUATED",
            "anomaly_detection_phase02": "IMPLEMENTED_AND_EVALUATED",
            "operating_health_index_phase03": "IMPLEMENTED_AND_EVALUATED",
            "proxy_prediction_training_phase04": "IMPLEMENTED_AND_EVALUATED",
            "proxy_probability_operational_release": "INSUFFICIENT_VALIDATION",
            "maintenance_engine_phase05": "IMPLEMENTED_AND_EVALUATED",
            "time_aware_evaluation_phase06": "IMPLEMENTED_AND_EVALUATED",
            "operational_false_alert_threshold": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
            "rul_prognostics": "NOT ESTIMABLE (NEEDS CONFIRMATION / ORGANIZER REQUIREMENT UNRESOLVED)",
            "site_critical_limits": "CONFIGURATION REQUIRED",
            "emergency_loading_envelope": "CONFIGURATION REQUIRED",
        }

        report = {
            "report_version": "1.0.0",
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_provenance": {
                "source_path": str(self.data_source_path) if self.data_source_path else "IN_MEMORY",
                "sha256_hash": file_hash,
                "total_rows": total_rows,
                "timestamp_range": {
                    "start": t_min,
                    "end": t_max,
                },
                "split_definitions": {
                    "train_end": SPLIT_TRAIN_END,
                    "val_end": SPLIT_VAL_END,
                },
            },
            "split_accounting": split_accounting,
            "thermal_evaluation": thermal_evaluation,
            "anomaly_evaluation": anomaly_evaluation,
            "forecast_evaluation": forecast_evaluation,
            "health_index_validation": hi_fixtures,
            "maintenance_validation": maint_scenarios,
            "capability_statuses": capability_statuses,
        }

        return report

    def save_report(
        self,
        output_path: Path | str = DEFAULT_REPORT_OUTPUT_PATH,
    ) -> Path:
        """Run all evaluations and persist JSON report to disk."""
        report = self.run_all()
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return p


def run_comprehensive_evaluation(
    canonical_df: pd.DataFrame,
    features_df: pd.DataFrame | None = None,
    thermal_residuals_oof: pd.Series | None = None,
    data_source_path: Path | str | None = None,
    output_path: Path | str = DEFAULT_REPORT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Functional entrypoint running time-aware evaluation and saving artifact."""
    harness = EvaluationHarness(
        canonical_df=canonical_df,
        features_df=features_df,
        thermal_residuals_oof=thermal_residuals_oof,
        data_source_path=data_source_path,
    )
    report = harness.run_all()
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report
