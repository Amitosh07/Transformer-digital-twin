"""Thermal Twin evaluation against permitted baselines on held-out chronological partitions.

Phase 06 — Time-Aware Evaluation:
Permitted Baselines:
1. Prior oil observation (persistence baseline): T_hat_t = T_{t-1} when dt <= 0.5h.
2. Ambient + training-median offset baseline: T_hat_t = A_t + median(T_train - A_train).
3. Ambient-only dynamic baseline: first-order model with ambient only (bJ = 0).

Metrics:
- MAE, RMSE, Bias (T - T_hat)
- Residual quantiles (Q0.01, Q0.05, Q0.50, Q0.95, Q0.99)
- Held-out improvement versus baseline
- Prediction coverage and thermal readiness
- Operational shift across chronological periods
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ThermalMetrics:
    mae: float | str
    rmse: float | str
    bias: float | str
    evaluated_count: int
    ready_count: int
    total_count: int
    coverage_ratio: float
    residual_quantiles: dict[str, float | str]


def fit_ambient_offset_baseline(train_df: pd.DataFrame) -> float:
    """Fit ambient offset strictly on training partition: median(T_train - A_train)."""
    valid = train_df["oil_temperature"].notna() & train_df["ambient_temperature"].notna()
    if not valid.any():
        return 0.0
    diff = train_df.loc[valid, "oil_temperature"] - train_df.loc[valid, "ambient_temperature"]
    return float(diff.median())


def fit_ambient_dynamic_baseline(
    train_df: pd.DataFrame,
    warmup_epsilon: float = 0.05,
) -> ThermalTwinConfig:
    """Fit ambient-only first-order dynamic baseline (bJ = 0) strictly on training clean runs."""
    from ml.thermal.calibration import extract_clean_training_runs

    clean_runs = extract_clean_training_runs(train_df)
    if not clean_runs:
        return ThermalTwinConfig(b0=0.0, bA=1.0, bJ=0.0, tau_hours=0.5)

    def objective(params: np.ndarray) -> float:
        b0, bA, tau = params
        warmup_required = -tau * np.log(warmup_epsilon)
        errors: list[float] = []

        for r in clean_runs:
            T = r["oil_temperature"].to_numpy()
            A = r["ambient_temperature"].to_numpy()
            dt = r["dt"].to_numpy()
            n = len(r)
            if n < 2:
                continue

            t_model = T[0]
            elapsed = 0.0
            for i in range(1, n):
                step_dt = dt[i]
                elapsed += step_dt
                alpha = np.exp(-step_dt / tau)
                t_inf = b0 + bA * A[i]
                t_model = t_model * alpha + t_inf * (1.0 - alpha)

                if elapsed >= warmup_required:
                    err = T[i] - t_model
                    # Pseudo-Huber loss
                    delta = 2.0
                    errors.append(delta**2 * (np.sqrt(1.0 + (err / delta)**2) - 1.0))

        return float(np.mean(errors)) if errors else 1e6

    # Initial guess & bounds: b0 in [-15, 15], bA in [0.5, 2.0], tau in [0.1, 5.0]
    res = minimize(
        objective,
        x0=[-2.0, 1.1, 0.5],
        bounds=[(-15.0, 15.0), (0.5, 2.0), (0.1, 5.0)],
        method="L-BFGS-B",
    )
    b0, bA, tau = res.x
    return ThermalTwinConfig(b0=float(b0), bA=float(bA), bJ=0.0, tau_hours=float(tau))


def compute_thermal_error_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    total_count: int,
    ready_count: int,
) -> dict[str, Any]:
    """Calculate MAE, RMSE, Bias, and quantiles on valid predictions."""
    valid_mask = np.isfinite(actual) & np.isfinite(predicted)
    n_eval = int(np.sum(valid_mask))

    if n_eval == 0:
        return {
            "mae": "NOT ESTIMABLE (zero valid evaluated instances)",
            "rmse": "NOT ESTIMABLE (zero valid evaluated instances)",
            "bias": "NOT ESTIMABLE (zero valid evaluated instances)",
            "evaluated_count": 0,
            "ready_count": ready_count,
            "total_count": total_count,
            "coverage_ratio": 0.0,
            "residual_quantiles": {},
        }

    err = actual[valid_mask] - predicted[valid_mask]
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))

    qs = [0.01, 0.05, 0.50, 0.95, 0.99]
    q_vals = {f"q_{int(q*100):02d}": float(np.quantile(err, q)) for q in qs}

    return {
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "evaluated_count": n_eval,
        "ready_count": ready_count,
        "total_count": total_count,
        "coverage_ratio": float(n_eval / total_count) if total_count > 0 else 0.0,
        "residual_quantiles": q_vals,
    }


def evaluate_thermal_twin_and_baselines(
    partition_df: pd.DataFrame,
    twin_config: ThermalTwinConfig,
    ambient_offset: float,
    ambient_dynamic_config: ThermalTwinConfig,
) -> dict[str, Any]:
    """Evaluate thermal twin and all three permitted baselines on a chronological partition."""
    df = partition_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["dt"] = df["timestamp"].diff().dt.total_seconds() / 3600.0

    # 1. Thermal Twin run
    twin = ThermalTwin(config=twin_config)
    res_twin = twin.run(df)
    t_actual = df["oil_temperature"].to_numpy(dtype="float64")
    t_twin_pred = res_twin["thermal_model_temperature"].to_numpy(dtype="float64")
    twin_ready = (res_twin["thermal_readiness"] == "READY").to_numpy()

    # Twin metrics only on READY instances
    twin_eval_pred = np.where(twin_ready, t_twin_pred, np.nan)
    metrics_twin = compute_thermal_error_metrics(
        t_actual, twin_eval_pred, total_count=len(df), ready_count=int(twin_ready.sum())
    )

    # 2. Baseline 1: Ambient + median offset
    t_ambient = df["ambient_temperature"].to_numpy(dtype="float64")
    t_amb_pred = t_ambient + ambient_offset
    metrics_amb_offset = compute_thermal_error_metrics(
        t_actual, t_amb_pred, total_count=len(df), ready_count=int(np.isfinite(t_amb_pred).sum())
    )

    # 3. Baseline 2: Prior oil observation (persistence, dt <= 0.5h)
    t_prior = df["oil_temperature"].shift(1).to_numpy(dtype="float64")
    dt = df["dt"].to_numpy(dtype="float64")
    valid_prior = (dt <= 0.5) & np.isfinite(t_prior)
    t_prior_pred = np.where(valid_prior, t_prior, np.nan)
    metrics_persistence = compute_thermal_error_metrics(
        t_actual, t_prior_pred, total_count=len(df), ready_count=int(valid_prior.sum())
    )

    # 4. Baseline 3: Ambient-only dynamic baseline
    dynamic_amb_twin = ThermalTwin(config=ambient_dynamic_config)
    res_amb_dyn = dynamic_amb_twin.run(df)
    t_amb_dyn_pred = res_amb_dyn["thermal_model_temperature"].to_numpy(dtype="float64")
    amb_dyn_ready = (res_amb_dyn["thermal_readiness"] == "READY").to_numpy()
    amb_dyn_eval_pred = np.where(amb_dyn_ready, t_amb_dyn_pred, np.nan)
    metrics_amb_dynamic = compute_thermal_error_metrics(
        t_actual, amb_dyn_eval_pred, total_count=len(df), ready_count=int(amb_dyn_ready.sum())
    )

    # Comparison / improvement
    mae_twin = metrics_twin["mae"] if isinstance(metrics_twin["mae"], (int, float)) else None
    mae_amb = metrics_amb_offset["mae"] if isinstance(metrics_amb_offset["mae"], (int, float)) else None

    improvement_vs_amb_offset = (
        float(mae_amb - mae_twin) if (mae_twin is not None and mae_amb is not None) else "NOT ESTIMABLE"
    )

    # Operational shift statistics
    valid_oil = df["oil_temperature"].dropna()
    valid_amb = df["ambient_temperature"].dropna()

    operational_shift = {
        "mean_observed_oil_temp": float(valid_oil.mean()) if not valid_oil.empty else "NOT ESTIMABLE",
        "std_observed_oil_temp": float(valid_oil.std()) if not valid_oil.empty else "NOT ESTIMABLE",
        "mean_ambient_temp": float(valid_amb.mean()) if not valid_amb.empty else "NOT ESTIMABLE",
        "std_ambient_temp": float(valid_amb.std()) if not valid_amb.empty else "NOT ESTIMABLE",
    }

    return {
        "thermal_twin": metrics_twin,
        "baseline_ambient_offset": metrics_amb_offset,
        "baseline_prior_observation": metrics_persistence,
        "baseline_ambient_dynamic": metrics_amb_dynamic,
        "improvement_over_ambient_offset_mae": improvement_vs_amb_offset,
        "operational_shift": operational_shift,
    }
