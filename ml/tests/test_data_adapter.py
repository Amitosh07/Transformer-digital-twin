"""Unit tests for the five-source canonical telemetry adapter."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from ml.adaptors.data_adapter import (
    AGGREGATION_RULES,
    DataAdapterError,
    PROCESSED_OUTPUT_PATH,
    build_canonical_telemetry,
    load_resolved_source_datasets,
    parse_timestamp,
    resolve_duplicates,
)


def _row(columns: list[str], timestamp: str, value: float = 1.0) -> dict[str, object]:
    return {"DeviceTimeStamp": timestamp, **{column: value for column in columns}}


def _write_sources(root: Path, *, overview_rows: list[dict[str, object]] | None = None, current_rows: list[dict[str, object]] | None = None) -> None:
    source_rows: dict[str, list[dict[str, object]]] = {}
    for name, rules in AGGREGATION_RULES.items():
        columns = [column for group in rules.values() for column in group]
        source_rows[name] = [_row(columns, "2026-01-01 00:00:00")]
    source_rows["CurrentVoltage.csv"][0].update({"VL12": 11, "VL23": 12, "VL31": 13})
    if overview_rows is not None:
        source_rows["Overview.csv"] = overview_rows
    if current_rows is not None:
        source_rows["CurrentVoltage.csv"] = current_rows
    for name, rows in source_rows.items():
        pd.DataFrame(rows).to_csv(root / name, index=False)


class DataAdapterTests(unittest.TestCase):
    def test_adapter_applies_duplicate_rules_and_canonicalizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            overview = [
                _row([column for fields in AGGREGATION_RULES["Overview.csv"].values() for column in fields], "2026-01-01 00:00:00", 1),
                _row([column for fields in AGGREGATION_RULES["Overview.csv"].values() for column in fields], "2026-01-01 00:00:00", 3),
            ]
            overview[0].update({"OTI_A": 0, "OTI_T": 0, "MOG_A": 0})
            overview[1].update({"OTI_A": 1, "OTI_T": 1, "MOG_A": 1})
            total = _row([column for fields in AGGREGATION_RULES["TotalPower.csv"].values() for column in fields], "2026-01-01 00:00:00", 5)
            total_second = total | {"KWH": 99, "KWH_I": 98, "KVARH": 97, "KW": 9}
            _write_sources(data_dir, overview_rows=overview)
            pd.DataFrame([total, total_second]).to_csv(data_dir / "TotalPower.csv", index=False)

            result = build_canonical_telemetry(data_dir, transformer_id="TEST-1")

            self.assertEqual(result["transformer_id"].tolist(), ["TEST-1"])
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(result["timestamp"]))
            self.assertFalse({"VL12", "VL23", "VL31"}.intersection(result.columns))
            self.assertAlmostEqual(result.loc[0, "oil_temperature"], 2)
            self.assertEqual(result.loc[0, "oil_temp_alarm"], 1)
            self.assertEqual(result.loc[0, "oil_temp_trip"], 1)
            self.assertEqual(result.loc[0, "magnetic_oil_gauge_alarm"], 1)
            self.assertEqual(result.loc[0, "energy_kwh"], 99)
            self.assertAlmostEqual(result.loc[0, "active_power_total"], 7)
            self.assertFalse(set(AGGREGATION_RULES["Power.csv"]["mean"]).intersection(result.columns))
            self.assertTrue(PROCESSED_OUTPUT_PATH.is_file())

            resolved_total = resolve_duplicates(
                parse_timestamp(pd.DataFrame([total, total_second]), "TotalPower.csv"), "TotalPower.csv"
            )
            self.assertEqual(resolved_total.loc[0, "KWH"], 99)
            self.assertEqual(resolved_total.loc[0, "KWH_I"], 98)
            self.assertEqual(resolved_total.loc[0, "KVARH"], 97)
            source_frames = load_resolved_source_datasets(data_dir)
            self.assertIn("WL1", source_frames["Power.csv"].columns)

    def test_identical_duplicates_collapse_to_one_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            current = pd.read_csv(data_dir / "CurrentVoltage.csv")
            pd.concat([current, current], ignore_index=True).to_csv(data_dir / "CurrentVoltage.csv", index=False)
            result = build_canonical_telemetry(data_dir)
            self.assertEqual(len(result), 1)
            self.assertTrue(result["timestamp"].is_unique)

    def test_outer_alignment_keeps_missing_readings_and_reports_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            overview = pd.read_csv(data_dir / "Overview.csv")
            overview.loc[0, "DeviceTimeStamp"] = "2026-01-01 00:15:00"
            overview.to_csv(data_dir / "Overview.csv", index=False)
            result = build_canonical_telemetry(data_dir)
            self.assertTrue(result["timestamp"].is_unique)
            self.assertEqual(len(result), 2)
            self.assertEqual(result["oil_temperature"].isna().sum(), 1)

    def test_invalid_timestamp_raises_understandable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            current = pd.read_csv(data_dir / "CurrentVoltage.csv")
            current.loc[0, "DeviceTimeStamp"] = "not-a-timestamp"
            current.to_csv(data_dir / "CurrentVoltage.csv", index=False)
            with self.assertRaisesRegex(DataAdapterError, "invalid DeviceTimeStamp"):
                build_canonical_telemetry(data_dir)

    def test_adapter_never_modifies_raw_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            before = {path.name: sha256(path.read_bytes()).hexdigest() for path in data_dir.glob("*.csv")}
            build_canonical_telemetry(data_dir)
            after = {path.name: sha256(path.read_bytes()).hexdigest() for path in data_dir.glob("*.csv")}
            self.assertEqual(after, before)
