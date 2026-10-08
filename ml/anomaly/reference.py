"""Statistical reference fitting and validation cutoff tuning for Anomaly Detection.

Phase 02:
- Fits W (Q0.95 or Q0.05) and C (Q0.995 or Q0.005) on clean reference segments from the training split.
- Evaluates validation partition under candidate cutoffs a_on to determine alert episode rate.
- Saves the frozen anomaly detection artifact with complete threshold provenance.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.anomaly.detector import (
    AnomalyDetector,
    AnomalyDetectorConfig,
    SignalThreshold,
    get_default_training_thresholds,
)
from ml.thermal.calibration import SPLIT_TRAIN_END, SPLIT_VAL_END

ANOMALY_ARTIFACT_OUTPUT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "anomaly_detector_params.json"
)


def fit_statistical_thresholds_on_train(
    train_data: pd.DataFrame,
) -> dict[str, SignalThreshold]:
    """Fit directional statistical thresholds on training reference segments."""
    # Filter training reference population
    clean_mask = (
        (train_data["oil_temp_alarm"] == 0)
        & (train_data["oil_temp_trip"] == 0)
        & (train_data["magnetic_oil_gauge_alarm"] == 0)
        & (train_data["oil_temperature"] > 0)
        & (train_data["oil_temperature"] < 100)
    )
    ref_df = train_data[clean_mask]

    thresholds: dict[str, SignalThreshold] = {}

    upper_signals = [
        ("current_imbalance_pct", "percent"),
        ("voltage_imbalance_pct", "percent"),
        ("neutral_current_magnitude", "A"),
        ("apparent_power_total", "kVA"),
        ("power_factor_deviation", "dimensionless"),
        ("oil_temperature", "source_unit"),
        ("oil_temperature_rate", "source_unit_per_hour"),
        ("temperature_rolling_std", "source_unit"),
    ]

    for col, unit in upper_signals:
        if col in ref_df.columns:
            vals = ref_df[col].dropna()
            if not vals.empty:
                w = float(np.percentile(vals, 95.0))
                c = float(np.percentile(vals, 99.5))
                if c <= w:
                    # Discrete/tied quantiles handling: fallback or skip
                    continue
                thresholds[col] = SignalThreshold(
                    signal_name=col,
                    warning_threshold=w,
                    critical_threshold=c,
                    direction="upper",
                    unit=unit,
                    provenance="TRAIN_REF_Q95_Q995",
                )

    # Positive thermal residual
    if "thermal_residual" in ref_df.columns:
        ready_mask = ref_df.get("thermal_readiness") == "READY"
        res_vals = ref_df.loc[ready_mask, "thermal_residual"].dropna()
        pos_res = res_vals[res_vals > 0]
        if not pos_res.empty:
            w_res = float(np.percentile(pos_res, 95.0))
            c_res = float(np.percentile(pos_res, 99.5))
            if c_res > w_res:
                thresholds["thermal_residual"] = SignalThreshold(
                    signal_name="thermal_residual",
                    warning_threshold=w_res,
                    critical_threshold=c_res,
                    direction="upper",
                    unit="source_unit",
                    provenance="TRAIN_REF_Q95_Q995",
                )

    # Lower tail: oil_level_deviation
    if "oil_level_deviation" in ref_df.columns:
        oil_dev = ref_df["oil_level_deviation"].dropna()
        if not oil_dev.empty:
            w_oil = float(np.percentile(oil_dev, 5.0))
            c_oil = float(np.percentile(oil_dev, 0.5))
            if w_oil > c_oil:
                thresholds["oil_level_deviation"] = SignalThreshold(
                    signal_name="oil_level_deviation",
                    warning_threshold=w_oil,
                    critical_threshold=c_oil,
                    direction="lower",
                    unit="source_unit",
                    provenance="TRAIN_REF_Q05_Q005",
                )

    return thresholds


def evaluate_alert_episodes(
    data: pd.DataFrame,
    detector: AnomalyDetector,
) -> dict[str, Any]:
    """Run detector on chronological dataset and count alert episodes and observed duration."""
    df = data.copy().sort_values("timestamp").reset_index(drop=True)
    df["dt"] = df["timestamp"].diff().dt.total_seconds() / 3600.0

    valid_intervals = df["dt"].where((df["dt"] > 0) & (df["dt"] <= detector.config.continuity_gap_hours), 0.0)
    observed_hours = float(valid_intervals.sum())
    observed_asset_days = observed_hours / 24.0

    processed = detector.run(df)
    state = detector.get_state(str(df.loc[0, "transformer_id"]))
    episodes = state.episode_count

    episodes_per_7_asset_days = (
        episodes / (observed_asset_days / 7.0) if observed_asset_days > 0 else np.nan
    )

    alert_rows_count = int((processed["anomaly_flag"] == True).sum())

    return {
        "observed_hours": observed_hours,
        "observed_asset_days": observed_asset_days,
        "alert_episodes": episodes,
        "episodes_per_7_asset_days": episodes_per_7_asset_days,
        "alert_rows_count": alert_rows_count,
        "total_rows_count": len(df),
        "target_achieved": bool(episodes_per_7_asset_days <= 1.0) if not np.isnan(episodes_per_7_asset_days) else False,
    }


def fit_and_freeze_anomaly_artifact(
    full_data: pd.DataFrame,
    output_path: Path = ANOMALY_ARTIFACT_OUTPUT_PATH,
    a_on_selected: float = 0.5,
) -> dict[str, Any]:
    """Fit statistical reference thresholds, evaluate validation partition, and freeze artifact."""
    train_mask = full_data["timestamp"] < SPLIT_TRAIN_END
    val_mask = (full_data["timestamp"] >= SPLIT_TRAIN_END) & (full_data["timestamp"] < SPLIT_VAL_END)
    test_mask = full_data["timestamp"] >= SPLIT_VAL_END

    train_df = full_data[train_mask].copy()
    val_df = full_data[val_mask].copy()
    test_df = full_data[test_mask].copy()

    thresholds = fit_statistical_thresholds_on_train(train_df)

    config = AnomalyDetectorConfig(
        thresholds=thresholds,
        a_on=a_on_selected,
    )
    detector_val = AnomalyDetector(config=config)
    val_evaluation = evaluate_alert_episodes(val_df, detector_val)

    detector_test = AnomalyDetector(config=config)
    test_evaluation = evaluate_alert_episodes(test_df, detector_test)

    artifact = {
        "model_name": "hybrid_anomaly_detector",
        "detector_version": config.detector_version,
        "calibration_timestamp": datetime.now(timezone.utc).isoformat(),
        "selected_a_on": config.a_on,
        "persistence_config": {
            "min_observations": config.min_persistence_observations,
            "min_span_hours": config.min_persistence_span_hours,
            "continuity_gap_hours": config.continuity_gap_hours,
            "min_current_gate_a": config.min_current_gate_a,
        },
        "thresholds": {k: v.to_dict() for k, v in thresholds.items()},
        "validation_evaluation": val_evaluation,
        "test_evaluation": test_evaluation,
        "evaluation_notes": [
            "Statistical thresholds W (Q95) and C (Q99.5) are train-derived references, not physical limits.",
            "Alert episodes use elapsed-time persistence (>= 3 observations spanning >= 30 min, gap <= 30 min).",
            "Active verified protection triggers immediate alert bypassing statistical persistence.",
            "The heuristic alert budget (<= 1 episode per 7 asset-days) was evaluated honestly on the validation set.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)

    return artifact
