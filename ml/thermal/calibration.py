"""Chronological calibration, baseline evaluation, and OOF residual generation for Thermal Twin.

Phase 01 Finalization:
- Chronological split boundaries: train before 2019-11-23 11:45; validation 2019-11-23 11:45 to 2020-02-13 11:15; test thereafter.
- Constrained optimization of parameters [b0, bA, bJ, tau].
- Baseline models: Ambient + median offset, Persistence (previous observation).
- Out-of-fold / chronological held-out residual generation for downstream Phase 02 and 04 consumption.
- Parameter artifact export with complete provenance, version, and metrics.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ml.thermal.thermal_twin import (
    ThermalModelMode,
    ThermalTwin,
    ThermalTwinConfig,
    compute_current_forcing,
)

# Chronological partition boundaries from AUDIT_PLAN.md
SPLIT_TRAIN_END: str = "2019-11-23 11:45:00"
SPLIT_VAL_END: str = "2020-02-13 11:15:00"

ARTIFACT_OUTPUT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "thermal_twin_params.json"
)


def extract_clean_training_runs(
    train_df: pd.DataFrame,
    max_gap_hours: float = 0.5,
    min_run_length: int = 10,
) -> list[pd.DataFrame]:
    """Extract contiguous candidate segments during alarm-free, clean periods."""
    df = train_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["dt"] = df["timestamp"].diff().dt.total_seconds() / 3600.0

    if "J" not in df.columns:
        df["J"] = compute_current_forcing(df)

    clean_mask = (
        (df["oil_temp_alarm"] == 0)
        & (df["oil_temp_trip"] == 0)
        & (df["oil_temperature"] > 0)
        & (df["oil_temperature"] < 100)
        & (df["ambient_temperature"] > 0)
        & (df["ambient_temperature"] < 60)
        & df["oil_temperature"].notna()
        & df["ambient_temperature"].notna()
        & df["J"].notna()
    )

    runs: list[pd.DataFrame] = []
    curr_run: list[pd.Series] = []

    for idx, row in df.iterrows():
        if not clean_mask.loc[idx]:
            if len(curr_run) >= min_run_length:
                runs.append(pd.DataFrame(curr_run))
            curr_run = []
        else:
            if curr_run and (row["dt"] > max_gap_hours or pd.isna(row["dt"])):
                if len(curr_run) >= min_run_length:
                    runs.append(pd.DataFrame(curr_run))
                curr_run = []
            curr_run.append(row)

    if len(curr_run) >= min_run_length:
        runs.append(pd.DataFrame(curr_run))

    return runs


def fit_thermal_twin_parameters(
    clean_runs: list[pd.DataFrame],
    warmup_epsilon: float = 0.05,
) -> tuple[ThermalTwinConfig, dict[str, float]]:
    """Fit constrained parameters [b0, bA, bJ, tau] using robust Huber loss on warm-up data."""
    def simulate_and_get_errors(params: np.ndarray) -> np.ndarray:
        b0, bA, bJ, tau = params
        warmup_required = -tau * np.log(warmup_epsilon)
        errors: list[float] = []

        for r in clean_runs:
            T = r["oil_temperature"].to_numpy()
            A = r["ambient_temperature"].to_numpy()
            J = r["J"].to_numpy()
            dt = r["dt"].to_numpy()
            n = len(r)

            state_T = T[0]
            warm_h = 0.0

            for i in range(1, n):
                u_prev = b0 + bA * A[i - 1] + bJ * J[i - 1]
                cur_dt = dt[i]
                pred = u_prev + (state_T - u_prev) * np.exp(-cur_dt / tau)
                warm_h += cur_dt

                if warm_h >= warmup_required and not np.isnan(T[i]):
                    errors.append(T[i] - pred)

                state_T = pred

        return np.array(errors, dtype="float64")

    def huber_objective(params: np.ndarray) -> float:
        errs = simulate_and_get_errors(params)
        if len(errs) == 0:
            return 1e6
        delta = 1.5
        abs_e = np.abs(errs)
        huber = np.where(abs_e <= delta, 0.5 * abs_e**2, delta * (abs_e - 0.5 * delta))
        return float(np.mean(huber))

    initial_guess = np.array([-2.0, 1.1, 1.0e-4, 0.5])
    bounds = [(-10.0, 10.0), (0.01, 3.0), (0.0, 1.0e-2), (0.05, 5.0)]

    res = minimize(huber_objective, initial_guess, bounds=bounds, method="L-BFGS-B")

    b0, bA, bJ, tau = res.x
    config = ThermalTwinConfig(
        b0=float(b0),
        bA=float(bA),
        bJ=float(bJ),
        tau_hours=float(tau),
        mode=ThermalModelMode.PUBLIC_EMPIRICAL,
        temperature_unit="SOURCE_UNVERIFIED",
    )

    final_errs = simulate_and_get_errors(res.x)
    metrics = {
        "train_mae": float(np.mean(np.abs(final_errs))),
        "train_rmse": float(np.sqrt(np.mean(final_errs**2))),
        "train_bias": float(np.mean(final_errs)),
        "samples_evaluated": len(final_errs),
    }

    return config, metrics


def evaluate_thermal_twin_on_partition(
    df: pd.DataFrame,
    config: ThermalTwinConfig,
) -> dict[str, float]:
    """Evaluate thermal twin on a chronological partition, calculating metrics only on ready residuals."""
    twin = ThermalTwin(config=config)
    processed = twin.run(df)

    res = processed["thermal_residual"].dropna()
    if res.empty:
        return {"mae": np.nan, "rmse": np.nan, "bias": np.nan, "ready_count": 0}

    return {
        "mae": float(np.mean(np.abs(res))),
        "rmse": float(np.sqrt(np.mean(res**2))),
        "bias": float(np.mean(res)),
        "ready_count": len(res),
        "total_count": len(df),
    }


def evaluate_baselines_on_partition(
    df: pd.DataFrame,
    median_train_offset: float = 2.0,
) -> dict[str, Any]:
    """Compute baseline metrics for comparison: Ambient + offset, and Persistence."""
    part = df.copy().sort_values("timestamp").reset_index(drop=True)
    part["dt"] = part["timestamp"].diff().dt.total_seconds() / 3600.0

    valid_mask = part["oil_temperature"].notna() & part["ambient_temperature"].notna()

    # Ambient + median offset baseline
    y = part.loc[valid_mask, "oil_temperature"]
    y_pred_med = part.loc[valid_mask, "ambient_temperature"] + median_train_offset
    err_med = y - y_pred_med

    # Persistence baseline (dt <= 30 min)
    persist_mask = valid_mask & (part["dt"] <= 0.5) & part["oil_temperature"].shift(1).notna()
    err_persist = part.loc[persist_mask, "oil_temperature"] - part["oil_temperature"].shift(1).loc[persist_mask]

    return {
        "ambient_offset": {
            "mae": float(np.mean(np.abs(err_med))) if not err_med.empty else np.nan,
            "rmse": float(np.sqrt(np.mean(err_med**2))) if not err_med.empty else np.nan,
            "bias": float(np.mean(err_med)) if not err_med.empty else np.nan,
        },
        "persistence": {
            "mae": float(np.mean(np.abs(err_persist))) if not err_persist.empty else np.nan,
            "rmse": float(np.sqrt(np.mean(err_persist**2))) if not err_persist.empty else np.nan,
            "bias": float(np.mean(err_persist)) if not err_persist.empty else np.nan,
        },
    }


def generate_chronological_oof_residuals(
    canonical_df: pd.DataFrame,
    config: ThermalTwinConfig,
    n_folds: int = 3,
) -> pd.Series:
    """Generate chronological out-of-fold residuals for training downstream phases.

    Partitions training data into chronological contiguous folds. Each fold k is evaluated
    using a model fitted strictly on earlier data folds, preventing in-sample residual leakage.
    """
    train_mask = canonical_df["timestamp"] < SPLIT_TRAIN_END
    train_df = canonical_df[train_mask].copy().sort_values("timestamp").reset_index(drop=True)

    fold_size = len(train_df) // n_folds
    oof_residuals = pd.Series(np.nan, index=canonical_df.index, dtype="float64")

    # Run chronological expanding-window thermal twin
    for fold in range(1, n_folds):
        train_sub = train_df.iloc[: fold * fold_size]
        val_sub = train_df.iloc[fold * fold_size : (fold + 1) * fold_size if fold < n_folds - 1 else len(train_df)]

        # Fit parameters strictly on train_sub
        clean_runs = extract_clean_training_runs(train_sub)
        fold_config, _ = fit_thermal_twin_parameters(clean_runs)

        # Run on val_sub
        twin = ThermalTwin(config=fold_config)
        processed = twin.run(val_sub)

        # Map back to original indices
        orig_indices = canonical_df[train_mask].sort_values("timestamp").index[
            fold * fold_size : (fold + 1) * fold_size if fold < n_folds - 1 else len(train_df)
        ]
        oof_residuals.loc[orig_indices] = processed["thermal_residual"].to_numpy()

    return oof_residuals


def run_full_calibration_and_save_artifact(
    canonical_df: pd.DataFrame,
    output_path: Path = ARTIFACT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Run complete calibration workflow and save the frozen parameter bundle."""
    train_df = canonical_df[canonical_df["timestamp"] < SPLIT_TRAIN_END].copy()
    val_df = canonical_df[
        (canonical_df["timestamp"] >= SPLIT_TRAIN_END) & (canonical_df["timestamp"] < SPLIT_VAL_END)
    ].copy()
    test_df = canonical_df[canonical_df["timestamp"] >= SPLIT_VAL_END].copy()

    # Extract clean segments and fit
    clean_runs = extract_clean_training_runs(train_df)
    config, train_metrics = fit_thermal_twin_parameters(clean_runs)

    # Evaluate partitions
    val_metrics = evaluate_thermal_twin_on_partition(val_df, config)
    test_metrics = evaluate_thermal_twin_on_partition(test_df, config)

    # Median offset baseline from train
    clean_train_rows = train_df[
        (train_df["oil_temp_alarm"] == 0)
        & (train_df["oil_temp_trip"] == 0)
        & (train_df["oil_temperature"] < 100)
    ]
    median_train_offset = float(
        np.median(clean_train_rows["oil_temperature"] - clean_train_rows["ambient_temperature"])
    )

    val_baselines = evaluate_baselines_on_partition(val_df, median_train_offset)
    test_baselines = evaluate_baselines_on_partition(test_df, median_train_offset)

    artifact = {
        "model_name": "thermal_twin_first_order",
        "parameter_version": config.parameter_version,
        "calibration_timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": config.mode.value,
        "temperature_unit": config.temperature_unit,
        "parameters": {
            "b0": config.b0,
            "bA": config.bA,
            "bJ": config.bJ,
            "tau_hours": config.tau_hours,
            "tau_minutes": config.tau_hours * 60.0,
            "continuity_gap_hours": config.continuity_gap_hours,
            "warmup_duration_hours": config.warmup_duration_hours,
        },
        "split_boundaries": {
            "train_end": SPLIT_TRAIN_END,
            "val_end": SPLIT_VAL_END,
        },
        "evaluation": {
            "train": train_metrics,
            "val": val_metrics,
            "test": test_metrics,
        },
        "baseline_comparison": {
            "val": val_baselines,
            "test": test_baselines,
        },
        "limitations_and_deferred_requirements": [
            "Source temperature units unverified (operating in PUBLIC_EMPIRICAL mode).",
            "WTI excluded from continuous temperature estimation.",
            "Asset nameplate ratings, loss ratios, and standards parameters remain CONFIGURATION REQUIRED.",
            "Standards-inspired mode (IEC 60076-7 / IS 2026-7) is defined but deferred pending rated constants.",
            "Statistical CRITICAL residual thresholds are deferred to Phase 02 learned severity.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)

    return artifact
