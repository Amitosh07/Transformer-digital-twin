"""
Historical replay engine — simulator_README §6.

Replays the public Kaggle dataset at adjustable speed through the canonical
adapter layer.  Source CSV column names are translated using the source
mapping defined in dataschema.md §19.

Flow:
  Dataset → Canonical Adapter → Replay Engine → Backend → Dashboard
"""

from __future__ import annotations

import datetime as _dt
import time
from pathlib import Path
from typing import Generator, Optional

import pandas as pd

from .schema import (
    EXCLUDED_SOURCE_FIELDS,
    SOURCE_TO_CANONICAL,
    TransformerRecord,
)


class ReplayEngine:
    """
    Loads one or more Kaggle CSV files, translates source columns to
    canonical names, and yields TransformerRecords at a controllable
    speed.

    Parameters
    ----------
    csv_paths : list[str | Path]
        Paths to one or more source CSV files.
    transformer_id : str
        Asset ID to stamp on every record (configurable baseline ID).
    speed_multiplier : float
        Playback speed.  1 = real time, 10 = 10× faster, etc.
    """

    def __init__(
        self,
        csv_paths: list[str | Path],
        transformer_id: str = "TX-001",
        speed_multiplier: float = 1.0,
    ) -> None:
        self.transformer_id = transformer_id
        self.speed_multiplier = max(0.01, speed_multiplier)
        self._df = self._load_and_adapt(csv_paths)

    # ------------------------------------------------------------------
    # Adapter layer — Kaggle columns → canonical fields (dataschema §19)
    # ------------------------------------------------------------------

    def _load_and_adapt(self, paths: list[str | Path]) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for p in paths:
            df = pd.read_csv(p)
            # Drop explicitly excluded columns (dataschema §5)
            df.drop(
                columns=[c for c in EXCLUDED_SOURCE_FIELDS if c in df.columns],
                inplace=True,
            )
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        # Merge all files on DeviceTimeStamp
        merged = frames[0]
        for other in frames[1:]:
            if "DeviceTimeStamp" in other.columns:
                merged = merged.merge(other, on="DeviceTimeStamp", how="outer", suffixes=("", "_dup"))
                # Remove any duplicate columns created by merge
                merged = merged[[c for c in merged.columns if not c.endswith("_dup")]]

        # Rename source → canonical
        rename_map = {
            src: canon
            for src, canon in SOURCE_TO_CANONICAL.items()
            if src in merged.columns
        }
        merged.rename(columns=rename_map, inplace=True)

        # Parse timestamp
        if "timestamp" in merged.columns:
            merged["timestamp"] = pd.to_datetime(merged["timestamp"], errors="coerce")
            merged.sort_values("timestamp", inplace=True)
            merged.dropna(subset=["timestamp"], inplace=True)
            merged.reset_index(drop=True, inplace=True)

        return merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def record_count(self) -> int:
        return len(self._df)

    def replay(self) -> Generator[TransformerRecord, None, None]:
        """
        Yield canonical records in time order, sleeping between records
        to simulate the original interval at the configured speed.
        """
        prev_ts: Optional[_dt.datetime] = None

        for _, row in self._df.iterrows():
            rec = self._row_to_record(row)

            if prev_ts is not None and rec.timestamp is not None and prev_ts is not None:
                gap = (rec.timestamp - prev_ts).total_seconds()
                sleep_s = max(0, gap / self.speed_multiplier)
                if sleep_s > 0:
                    time.sleep(sleep_s)

            prev_ts = rec.timestamp
            yield rec

    def all_records(self) -> list[TransformerRecord]:
        """Return all records immediately (no sleep) — useful for batch seeding."""
        records: list[TransformerRecord] = []
        for _, row in self._df.iterrows():
            records.append(self._row_to_record(row))
        return records

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _row_to_record(self, row: pd.Series) -> TransformerRecord:
        """
        Build a TransformerRecord from a row that already has canonical
        column names.  Missing data stays None — NOT converted to zero
        (dataschema §1.6).
        """

        def _get(field: str, cast=float):
            val = row.get(field)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            try:
                return cast(val)
            except (ValueError, TypeError):
                return None

        return TransformerRecord(
            transformer_id=self.transformer_id,
            timestamp=row.get("timestamp", _dt.datetime.now(_dt.timezone.utc)),
            phase_voltage_l1=_get("phase_voltage_l1"),
            phase_voltage_l2=_get("phase_voltage_l2"),
            phase_voltage_l3=_get("phase_voltage_l3"),
            current_l1=_get("current_l1"),
            current_l2=_get("current_l2"),
            current_l3=_get("current_l3"),
            neutral_current=_get("neutral_current"),
            oil_temperature=_get("oil_temperature"),
            winding_temperature=_get("winding_temperature"),
            ambient_temperature=_get("ambient_temperature"),
            oil_level=_get("oil_level"),
            oil_temp_alarm=_get("oil_temp_alarm", int),
            oil_temp_trip=_get("oil_temp_trip", int),
            magnetic_oil_gauge_alarm=_get("magnetic_oil_gauge_alarm", int),
            active_power_total=_get("active_power_total"),
            apparent_power_total=_get("apparent_power_total"),
            reactive_power_total=_get("reactive_power_total"),
            energy_kwh=_get("energy_kwh"),
            power_factor_l1=_get("power_factor_l1"),
            power_factor_l2=_get("power_factor_l2"),
            power_factor_l3=_get("power_factor_l3"),
        )
