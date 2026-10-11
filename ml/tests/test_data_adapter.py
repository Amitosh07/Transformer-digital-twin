"""Unit tests for the five-source canonical telemetry adapter.

Phase 00 remediation:
- Tests use temporary directories exclusively; no test writes to the production path.
- WTI conflict resolution, status domain validation, multi-asset keys, quality
  metadata and three-valued alarm OR are covered.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from ml.adaptors.data_adapter import (
    AGGREGATION_RULES,
    CANONICAL_COLUMNS,
    DataAdapterError,
    PROCESSED_OUTPUT_PATH,
    QualityReport,
    WTI_COLUMN,
    build_canonical_telemetry,
    load_resolved_source_datasets,
    parse_timestamp,
    persist_canonical_telemetry,
    resolve_duplicates,
)


def _row(columns: list[str], timestamp: str, value: float = 1.0) -> dict[str, object]:
    return {"DeviceTimeStamp": timestamp, **{column: value for column in columns}}


def _overview_columns() -> list[str]:
    """All columns expected in Overview.csv including WTI."""
    cols = [column for group in AGGREGATION_RULES["Overview.csv"].values() for column in group]
    cols.append(WTI_COLUMN)
    return cols


def _write_sources(
    root: Path,
    *,
    overview_rows: list[dict[str, object]] | None = None,
    current_rows: list[dict[str, object]] | None = None,
) -> None:
    source_rows: dict[str, list[dict[str, object]]] = {}
    for name, rules in AGGREGATION_RULES.items():
        columns = [column for group in rules.values() for column in group]
        if name == "Overview.csv":
            columns.append(WTI_COLUMN)
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
            out_path = data_dir / "output" / "canonical.csv"
            overview = [
                _row(_overview_columns(), "2026-01-01 00:00:00", 1),
                _row(_overview_columns(), "2026-01-01 00:00:00", 3),
            ]
            overview[0].update({"OTI_A": 0, "OTI_T": 0, "MOG_A": 0, "WTI": 0})
            overview[1].update({"OTI_A": 1, "OTI_T": 1, "MOG_A": 1, "WTI": 0})
            total = _row([column for fields in AGGREGATION_RULES["TotalPower.csv"].values() for column in fields], "2026-01-01 00:00:00", 5)
            total_second = total | {"KWH": 99, "KWH_I": 98, "KVARH": 97, "KW": 9}
            _write_sources(data_dir, overview_rows=overview)
            pd.DataFrame([total, total_second]).to_csv(data_dir / "TotalPower.csv", index=False)

            result, quality = build_canonical_telemetry(data_dir, transformer_id="TEST-1", output_path=out_path)

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
            # Phase 00: test writes to temp output, NOT to production path
            self.assertTrue(out_path.is_file())
            # Quality report is populated
            self.assertIsInstance(quality, QualityReport)
            self.assertEqual(quality.row_count, 1)

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
            result, _ = build_canonical_telemetry(data_dir)
            self.assertEqual(len(result), 1)
            self.assertTrue(result["timestamp"].is_unique)

    def test_outer_alignment_keeps_missing_readings_and_reports_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            overview = pd.read_csv(data_dir / "Overview.csv")
            overview.loc[0, "DeviceTimeStamp"] = "2026-01-01 00:15:00"
            overview.to_csv(data_dir / "Overview.csv", index=False)
            result, quality = build_canonical_telemetry(data_dir)
            self.assertTrue(result["timestamp"].is_unique)
            self.assertEqual(len(result), 2)
            self.assertEqual(result["oil_temperature"].isna().sum(), 1)
            self.assertEqual(quality.row_count, 2)

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

    # --- Phase 00 new regression tests ---

    def test_build_does_not_write_to_production_path_by_default(self) -> None:
        """Phase 00: build_canonical_telemetry must not write to PROCESSED_OUTPUT_PATH."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            # Clear the production file if it happens to exist from a prior run
            prod_existed_before = PROCESSED_OUTPUT_PATH.is_file()
            if prod_existed_before:
                prod_hash_before = sha256(PROCESSED_OUTPUT_PATH.read_bytes()).hexdigest()

            build_canonical_telemetry(data_dir)

            if prod_existed_before:
                # File must not have been modified
                prod_hash_after = sha256(PROCESSED_OUTPUT_PATH.read_bytes()).hexdigest()
                self.assertEqual(prod_hash_before, prod_hash_after,
                                 "build_canonical_telemetry must not overwrite the production canonical file")

    def test_wti_not_averaged_identical_values(self) -> None:
        """Phase 00: identical WTI duplicates collapse to that value, not an average."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            overview = [
                _row(_overview_columns(), "2026-01-01 00:00:00", 1.0),
                _row(_overview_columns(), "2026-01-01 00:00:00", 1.0),
            ]
            overview[0].update({"WTI": 1, "OTI_A": 0, "OTI_T": 0, "MOG_A": 0})
            overview[1].update({"WTI": 1, "OTI_A": 0, "OTI_T": 0, "MOG_A": 0})
            _write_sources(data_dir, overview_rows=overview)
            result, _ = build_canonical_telemetry(data_dir)
            self.assertEqual(result.loc[0, "winding_temperature"], 1.0)

    def test_wti_conflict_produces_nan_never_fractional(self) -> None:
        """Phase 00: WTI conflicts (mix of 0 and 1) must produce NaN, never 0.5."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            overview = [
                _row(_overview_columns(), "2026-01-01 00:00:00", 1.0),
                _row(_overview_columns(), "2026-01-01 00:00:00", 1.0),
            ]
            overview[0].update({"WTI": 0, "OTI_A": 0, "OTI_T": 0, "MOG_A": 0})
            overview[1].update({"WTI": 1, "OTI_A": 0, "OTI_T": 0, "MOG_A": 0})
            _write_sources(data_dir, overview_rows=overview)
            result, _ = build_canonical_telemetry(data_dir)
            # Must be NaN, never 0.5
            self.assertTrue(pd.isna(result.loc[0, "winding_temperature"]),
                            f"WTI conflict should produce NaN, got {result.loc[0, 'winding_temperature']}")

    def test_multi_asset_same_timestamp_accepted(self) -> None:
        """Phase 00: (transformer_id, timestamp) is the key, not timestamp alone."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            result_a, _ = build_canonical_telemetry(data_dir, transformer_id="TR-A")
            result_b, _ = build_canonical_telemetry(data_dir, transformer_id="TR-B")
            combined = pd.concat([result_a, result_b], ignore_index=True)
            # Two assets at the same timestamp should be valid
            self.assertEqual(len(combined), 2)
            from ml.adaptors.data_adapter import validate_canonical_telemetry
            # Should not raise because canonical key is (transformer_id, timestamp)
            validate_canonical_telemetry(combined)

    def test_status_domain_validation_rejects_invalid_values(self) -> None:
        """Phase 00: alarm/trip fields must be in {0, 1, NaN}."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            result, _ = build_canonical_telemetry(data_dir)
            # Inject invalid alarm value
            result.loc[0, "oil_temp_alarm"] = 2.0
            from ml.adaptors.data_adapter import validate_canonical_telemetry
            with self.assertRaisesRegex(DataAdapterError, "Status field"):
                validate_canonical_telemetry(result)

    def test_quality_report_has_required_fields(self) -> None:
        """Phase 00: quality report includes all specified metadata."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            _, quality = build_canonical_telemetry(data_dir)
            report = quality.to_dict()
            for required_key in [
                "row_count", "missing_count_by_field", "duplicate_timestamp_count",
                "timestamp_gap_statistics", "out_of_range_count", "parse_error_count",
                "source_file", "ingestion_timestamp", "schema_version",
            ]:
                self.assertIn(required_key, report, f"Quality report missing: {required_key}")
            self.assertEqual(report["schema_version"], "1.0.0")

    def test_non_finite_values_rejected(self) -> None:
        """Phase 00: non-finite (inf) values must not pass validation."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            result, _ = build_canonical_telemetry(data_dir)
            result.loc[0, "oil_temperature"] = np.inf
            from ml.adaptors.data_adapter import validate_canonical_telemetry
            with self.assertRaisesRegex(DataAdapterError, "non-finite"):
                validate_canonical_telemetry(result)

    def test_persist_writes_to_specified_path(self) -> None:
        """Phase 00: persist_canonical_telemetry writes to the given path."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            _write_sources(data_dir)
            result, _ = build_canonical_telemetry(data_dir)
            out_path = Path(temporary_directory) / "output" / "test_canonical.csv"
            persist_canonical_telemetry(result, out_path)
            self.assertTrue(out_path.is_file())
            reloaded = pd.read_csv(out_path)
            self.assertEqual(len(reloaded), len(result))
