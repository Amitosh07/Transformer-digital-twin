"""Chronological split definitions, target-horizon purging, and event accounting for Phase 06.

Phase 06 — Time-Aware Evaluation:
- Frozen chronological split boundaries derived from original union timeline.
- Target-horizon purge applied before split boundaries to prevent horizon overlap leakage.
- Elapsed observed duration accounting (excluding gaps > 30 minutes from exposure denominator).
- Data provenance and SHA-256 fingerprinting.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd

# Primary fixed split boundaries from AUDIT_PLAN.md & 06_EVALUATION.md
SPLIT_TRAIN_END: Final = "2019-11-23 11:45:00"
SPLIT_VAL_END: Final = "2020-02-13 11:15:00"

# Exploratory event-era split boundaries
EXPLORATORY_SPLIT_TRAIN_END: Final = "2019-08-01 00:00:00"
EXPLORATORY_SPLIT_VAL_END: Final = "2019-08-16 00:00:00"
EXPLORATORY_SPLIT_TEST_END: Final = "2019-09-04 00:00:00"

DEFAULT_HORIZON_HOURS: Final = 1.0
DEFAULT_MAX_GAP_HOURS: Final = 0.5


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute SHA-256 fingerprint of a file on disk."""
    p = Path(file_path)
    if not p.is_file():
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_adequately_observed_asset_days(
    timestamps: pd.Series | Sequence[pd.Timestamp],
    max_gap_hours: float = DEFAULT_MAX_GAP_HOURS,
) -> float:
    """Compute adequately observed asset-days using actual elapsed timestamps.

    Excludes intervals where dt > max_gap_hours (long continuity gaps) from exposure.
    Does NOT assume fixed 15-minute sampling cadence.
    """
    ts = pd.Series(pd.to_datetime(timestamps)).dropna().sort_values().reset_index(drop=True)
    if len(ts) < 2:
        return 0.0

    dt_hours = ts.diff().iloc[1:].dt.total_seconds() / 3600.0
    qualifying_dt = dt_hours[dt_hours <= max_gap_hours]
    total_qualifying_hours = float(qualifying_dt.sum())
    return float(total_qualifying_hours / 24.0)


@dataclass(frozen=True)
class PartitionAccounting:
    partition_name: str
    total_rows: int
    purged_rows: int
    eligible_rows: int
    censored_rows: int
    positive_rows: int
    negative_rows: int
    observed_asset_days: float
    start_timestamp: str | None
    end_timestamp: str | None


def partition_primary_chronological_splits(
    df: pd.DataFrame,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
    target_table: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Partition telemetry or analytics into Train, Validation, Test on original timeline.

    Applies target-horizon purge at split boundaries:
    - Train purge: samples in [SPLIT_TRAIN_END - horizon_hours, SPLIT_TRAIN_END)
    - Val purge: samples in [SPLIT_VAL_END - horizon_hours, SPLIT_VAL_END)
    """
    ts = pd.to_datetime(df["timestamp"])
    t_train_end = pd.Timestamp(SPLIT_TRAIN_END)
    t_val_end = pd.Timestamp(SPLIT_VAL_END)
    h = pd.Timedelta(hours=horizon_hours)

    train_purge_cutoff = t_train_end - h
    val_purge_cutoff = t_val_end - h

    train_mask = ts < train_purge_cutoff
    val_mask = (ts >= t_train_end) & (ts < val_purge_cutoff)
    test_mask = ts >= t_val_end

    return {
        "train": df.loc[train_mask].copy(),
        "val": df.loc[val_mask].copy(),
        "test": df.loc[test_mask].copy(),
        "train_purged": df.loc[(ts >= train_purge_cutoff) & (ts < t_train_end)].copy(),
        "val_purged": df.loc[(ts >= val_purge_cutoff) & (ts < t_val_end)].copy(),
    }


def partition_exploratory_splits(
    df: pd.DataFrame,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
) -> dict[str, pd.DataFrame]:
    """Partition into exploratory event-era subsets with target-horizon purge."""
    ts = pd.to_datetime(df["timestamp"])
    t_train_end = pd.Timestamp(EXPLORATORY_SPLIT_TRAIN_END)
    t_val_end = pd.Timestamp(EXPLORATORY_SPLIT_VAL_END)
    t_test_end = pd.Timestamp(EXPLORATORY_SPLIT_TEST_END)
    h = pd.Timedelta(hours=horizon_hours)

    train_mask = ts < (t_train_end - h)
    val_mask = (ts >= t_train_end) & (ts < (t_val_end - h))
    test_mask = (ts >= t_val_end) & (ts < t_test_end)
    surv_mask = ts >= t_test_end

    return {
        "train": df.loc[train_mask].copy(),
        "val": df.loc[val_mask].copy(),
        "test": df.loc[test_mask].copy(),
        "surveillance": df.loc[surv_mask].copy(),
        "train_purged": df.loc[(ts >= (t_train_end - h)) & (ts < t_train_end)].copy(),
        "val_purged": df.loc[(ts >= (t_val_end - h)) & (ts < t_val_end)].copy(),
    }
