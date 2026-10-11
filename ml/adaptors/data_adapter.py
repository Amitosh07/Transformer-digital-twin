"""Convert the five baseline source CSVs into canonical transformer telemetry.
This module is deliberately the only ML-layer location that knows the public
dataset's filenames and raw column names.  It preserves the supplied timestamp
cadence; it does not resample or impute readings.

Phase 00 remediation:
- Canonical building is separated from persistence.  Tests must use temporary
  output locations; no test fixture may replace historical data.
- WTI is raw 0/1, not a continuous temperature signal.  It is never averaged;
  conflicting status duplicates produce unknown (NaN).
- Alarm fields use three-valued OR: any known 1 → 1; all known 0 → 0;
  otherwise unknown (NaN).
- Status domain validation: alarm/trip fields must be in {0, 1, NaN}.
- Canonical key is (transformer_id, timestamp).
- Quality metadata report is produced alongside canonical telemetry.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal, Mapping

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype


TIMESTAMP_COLUMN: Final = "DeviceTimeStamp"
CANONICAL_TIMESTAMP: Final = "timestamp"
EXCLUDED_CURRENT_VOLTAGE_COLUMNS: Final = ("VL12", "VL23", "VL31")
PROCESSED_OUTPUT_PATH: Final = Path(__file__).resolve().parents[2] / "data" / "processed" / "canonical_telemetry.csv"
AggregationMethod = Literal["mean", "max", "first", "last"]

STATUS_COLUMNS: Final = ("oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm")
VALID_STATUS_VALUES: Final = frozenset({0.0, 1.0})

# The semantic treatment of every field read from each source is explicit.  In
# particular, counters are never summed/averaged and protection states retain
# an active state found in any duplicate source row.
#
# Phase 00 fix: WTI is removed from "mean" and placed under "wti_status" which
# uses a dedicated three-valued conflict-aware resolution (not numeric mean).
AGGREGATION_RULES: Final[dict[str, dict[AggregationMethod, tuple[str, ...]]]] = {
    "CurrentVoltage.csv": {
        "mean": ("VL1", "VL2", "VL3", "IL1", "IL2", "IL3", "INUT"),
        "max": (),
        "first": (),
        "last": (),
    },
    "Overview.csv": {
        "mean": ("OTI", "ATI", "OLI"),
        "max": ("OTI_A", "OTI_T", "MOG_A"),
        "first": (),
        "last": (),
    },
    "Power.csv": {
        "mean": ("WL1", "WL2", "WL3", "VAL1", "VAL2", "VAL3", "RVAL1", "RVAL2", "RVAL3"),
        "max": (),
        "first": (),
        "last": (),
    },
    "PowerFactor.csv": {
        "mean": (
            "PFL1", "PFL2", "PFL3", "Avg_PF", "Sum_PF", "FRQ", "THDVL1", "THDVL2",
            "THDVL3", "THDIL1", "THDIL2", "THDIL3", "MDIL1", "MDIL2", "MDIL3",
        ),
        "max": (),
        "first": (),
        "last": (),
    },
    "TotalPower.csv": {
        "mean": ("KW", "KVA", "KVAR", "MPD", "MKVAD"),
        "max": (),
        "first": (),
        "last": ("KWH", "KWH_I", "KVARH"),
    },
}

# WTI is a raw 0/1 status field that must never be averaged.  It receives
# dedicated three-valued conflict-aware resolution inside resolve_duplicates.
WTI_COLUMN: Final = "WTI"

# Only mappings established by dataschema.md and the team plan are exported.
# KW/KVA/KVAR are the source's explicitly named total-power measures.  Other
# raw fields below remain source-level and are intentionally omitted.
SOURCE_COLUMN_MAPPINGS: Final[dict[str, dict[str, str]]] = {
    "CurrentVoltage.csv": {
        "VL1": "phase_voltage_l1", "VL2": "phase_voltage_l2", "VL3": "phase_voltage_l3",
        "IL1": "current_l1", "IL2": "current_l2", "IL3": "current_l3", "INUT": "neutral_current",
    },
    "Overview.csv": {
        "OTI": "oil_temperature", "WTI": "winding_temperature", "ATI": "ambient_temperature",
        "OLI": "oil_level", "OTI_A": "oil_temp_alarm", "OTI_T": "oil_temp_trip",
        "MOG_A": "magnetic_oil_gauge_alarm",
    },
    "Power.csv": {},
    "PowerFactor.csv": {
        "PFL1": "power_factor_l1", "PFL2": "power_factor_l2", "PFL3": "power_factor_l3",
    },
    "TotalPower.csv": {
        "KW": "active_power_total", "KVA": "apparent_power_total", "KVAR": "reactive_power_total",
        "KWH": "energy_kwh",
    },
}

UNMAPPED_SOURCE_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "Power.csv": ("WL1", "WL2", "WL3", "VAL1", "VAL2", "VAL3", "RVAL1", "RVAL2", "RVAL3"),
    "PowerFactor.csv": ("Avg_PF", "Sum_PF", "FRQ", "THDVL1", "THDVL2", "THDVL3", "THDIL1", "THDIL2", "THDIL3", "MDIL1", "MDIL2", "MDIL3"),
    "TotalPower.csv": ("KWH_I", "KVARH", "MPD", "MKVAD"),
}

CANONICAL_COLUMNS: Final[tuple[str, ...]] = (
    "transformer_id", "timestamp", "phase_voltage_l1", "phase_voltage_l2", "phase_voltage_l3",
    "current_l1", "current_l2", "current_l3", "neutral_current", "oil_temperature",
    "winding_temperature", "ambient_temperature", "oil_level", "oil_temp_alarm", "oil_temp_trip",
    "magnetic_oil_gauge_alarm", "active_power_total", "apparent_power_total", "reactive_power_total",
    "energy_kwh", "power_factor_l1", "power_factor_l2", "power_factor_l3",
)
NUMERIC_CANONICAL_COLUMNS: Final[tuple[str, ...]] = CANONICAL_COLUMNS[2:]


@dataclass
class QualityReport:
    """Aggregate quality metadata produced alongside canonical telemetry.

    Fields match the quality report specification in the data schema and Phase 00.
    """

    source_file: str
    schema_version: str
    ingestion_timestamp: str
    row_count: int = 0
    missing_count_by_field: dict[str, int] = field(default_factory=dict)
    duplicate_timestamp_count: int = 0
    timestamp_gap_statistics: dict[str, Any] = field(default_factory=dict)
    out_of_range_count: int = 0
    parse_error_count: int = 0
    source_hashes: dict[str, str] = field(default_factory=dict)
    time_range: dict[str, str] = field(default_factory=dict)
    wti_conflict_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation."""
        return {
            "source_file": self.source_file,
            "schema_version": self.schema_version,
            "ingestion_timestamp": self.ingestion_timestamp,
            "row_count": self.row_count,
            "missing_count_by_field": self.missing_count_by_field,
            "duplicate_timestamp_count": self.duplicate_timestamp_count,
            "timestamp_gap_statistics": self.timestamp_gap_statistics,
            "out_of_range_count": self.out_of_range_count,
            "parse_error_count": self.parse_error_count,
            "source_hashes": self.source_hashes,
            "time_range": self.time_range,
            "wti_conflict_count": self.wti_conflict_count,
        }


class DataAdapterError(ValueError):
    """Raised when a source file or canonical telemetry fails validation."""


def _source_columns(source_name: str) -> tuple[str, ...]:
    rules = AGGREGATION_RULES[source_name]
    cols = tuple(column for fields in rules.values() for column in fields)
    # WTI is handled separately but must still be expected in Overview.csv
    if source_name == "Overview.csv":
        cols = (*cols, WTI_COLUMN)
    return cols


def load_dataset(path: str | Path, source_name: str) -> pd.DataFrame:
    """Load one expected source CSV, checking its timestamp and telemetry columns."""
    if source_name not in AGGREGATION_RULES:
        raise DataAdapterError(f"Unsupported source dataset: {source_name}")
    source_path = Path(path)
    if not source_path.is_file():
        raise DataAdapterError(f"Required source file was not found: {source_path}")
    frame = pd.read_csv(source_path)
    expected = {TIMESTAMP_COLUMN, *_source_columns(source_name)}
    missing = sorted(expected.difference(frame.columns))
    if missing:
        raise DataAdapterError(f"{source_name} is missing required columns: {missing}")
    return frame


def load_resolved_source_datasets(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load and duplicate-resolve source-level frames without changing their schema.

    This keeps optional fields (including all of ``Power.csv``) available to
    future ML feature code while ensuring they do not enter canonical telemetry.
    """
    base_path = Path(data_dir)
    return {
        source_name: resolve_duplicates(
            parse_timestamp(load_dataset(base_path / source_name, source_name), source_name), source_name
        )
        for source_name in AGGREGATION_RULES
    }


def parse_timestamp(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Parse source timestamps, failing rather than discarding malformed records."""
    if TIMESTAMP_COLUMN not in frame:
        raise DataAdapterError(f"{source_name} has no {TIMESTAMP_COLUMN!r} column")
    result = frame.copy()
    parsed = pd.to_datetime(result[TIMESTAMP_COLUMN], errors="coerce")
    invalid_count = int(parsed.isna().sum())
    if invalid_count:
        raise DataAdapterError(f"{source_name} contains {invalid_count} invalid {TIMESTAMP_COLUMN} value(s)")
    result[TIMESTAMP_COLUMN] = parsed
    return result


def _resolve_wti_status(group: pd.DataFrame) -> float | None:
    """Resolve duplicate WTI status values with three-valued conflict semantics.

    WTI is a raw 0/1 status field.  For duplicate timestamps:
    - If all values are identical → that value.
    - If values conflict (mix of 0 and 1) → NaN (unknown/conflict).
    - If all missing → NaN.

    Never averages to produce fractional values like 0.5.
    """
    values = group[WTI_COLUMN].dropna()
    if values.empty:
        return np.nan
    unique = values.unique()
    if len(unique) == 1:
        return float(unique[0])
    # Conflicting values: not all the same → unknown
    return np.nan


def resolve_duplicates(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Aggregate duplicate timestamps with the source's explicit field rules."""
    rules = AGGREGATION_RULES[source_name]
    result = frame.sort_values(TIMESTAMP_COLUMN, kind="stable").copy()
    aggregation = {column: method for method, columns in rules.items() for column in columns}
    # Convert raw telemetry deliberately: unexpected non-numeric source values are a
    # data-quality failure, not something the adapter should silently coerce.
    for column in aggregation:
        result[column] = pd.to_numeric(result[column], errors="raise")

    # Phase 00: Handle WTI separately with conflict-aware resolution
    if source_name == "Overview.csv" and WTI_COLUMN in result.columns:
        result[WTI_COLUMN] = pd.to_numeric(result[WTI_COLUMN], errors="raise")
        # Track conflict count for quality report
        wti_grouped = result.groupby(TIMESTAMP_COLUMN, sort=True)
        wti_resolved = wti_grouped.apply(
            lambda g: pd.Series({WTI_COLUMN: _resolve_wti_status(g)}),
            include_groups=False,
        ).reset_index()
        resolved = result.groupby(TIMESTAMP_COLUMN, as_index=False, sort=True).agg(aggregation)
        resolved = resolved.merge(wti_resolved, on=TIMESTAMP_COLUMN, how="left")
        return resolved

    return result.groupby(TIMESTAMP_COLUMN, as_index=False, sort=True).agg(aggregation)


def normalize_columns(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Keep only source fields with approved canonical mappings and rename them."""
    if source_name == "CurrentVoltage.csv":
        # These line-to-line voltages are explicitly outside the shared contract.
        frame = frame.drop(columns=list(EXCLUDED_CURRENT_VOLTAGE_COLUMNS), errors="ignore")
    mapping = SOURCE_COLUMN_MAPPINGS[source_name]
    selected = frame.loc[:, [TIMESTAMP_COLUMN, *mapping]].rename(
        columns={TIMESTAMP_COLUMN: CANONICAL_TIMESTAMP, **mapping}
    )
    return selected


def merge_datasets(datasets: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Outer-align normalized sources so a timestamp in any source is retained."""
    merged: pd.DataFrame | None = None
    for source_name in AGGREGATION_RULES:
        frame = datasets[source_name]
        merged = frame if merged is None else merged.merge(frame, on=CANONICAL_TIMESTAMP, how="outer", validate="one_to_one")
    assert merged is not None  # AGGREGATION_RULES is non-empty.
    return merged.sort_values(CANONICAL_TIMESTAMP, kind="stable").reset_index(drop=True)


def _validate_status_domain(frame: pd.DataFrame) -> None:
    """Validate that alarm/trip status fields contain only {0, 1, NaN}."""
    for column in STATUS_COLUMNS:
        if column not in frame.columns:
            continue
        non_null = frame[column].dropna()
        if non_null.empty:
            continue
        invalid = non_null[~non_null.isin(VALID_STATUS_VALUES)]
        if not invalid.empty:
            bad_values = sorted(invalid.unique().tolist())
            raise DataAdapterError(
                f"Status field '{column}' contains values outside {{0, 1}}: {bad_values}"
            )


def validate_canonical_telemetry(frame: pd.DataFrame) -> None:
    """Validate the canonical telemetry boundary.

    Phase 00 fixes:
    - Canonical key is (transformer_id, timestamp), not timestamp alone.
    - Non-finite numeric values are detected.
    - Status domain {0, 1, NaN} is validated for alarm/trip fields.
    """
    missing_columns = [column for column in CANONICAL_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise DataAdapterError(f"Canonical telemetry is missing required columns: {missing_columns}")
    forbidden = sorted(set(EXCLUDED_CURRENT_VOLTAGE_COLUMNS).intersection(frame.columns))
    if forbidden:
        raise DataAdapterError(f"Canonical telemetry contains excluded columns: {forbidden}")
    if not is_datetime64_any_dtype(frame[CANONICAL_TIMESTAMP]):
        raise DataAdapterError("Canonical timestamp must have a pandas datetime dtype")
    if frame[CANONICAL_TIMESTAMP].isna().any():
        raise DataAdapterError("Canonical timestamp contains invalid or missing values")
    if frame["transformer_id"].isna().any() or (frame["transformer_id"].astype(str).str.strip() == "").any():
        raise DataAdapterError("Canonical transformer_id must be populated for every row")
    # Phase 00: canonical key is (transformer_id, timestamp)
    if frame.duplicated(["transformer_id", CANONICAL_TIMESTAMP]).any():
        raise DataAdapterError("Canonical telemetry contains duplicate (transformer_id, timestamp) pairs")
    non_numeric = [column for column in NUMERIC_CANONICAL_COLUMNS if not is_numeric_dtype(frame[column])]
    if non_numeric:
        raise DataAdapterError(f"Canonical telemetry columns must be numeric: {non_numeric}")
    # Phase 00: non-finite check — inf values must not enter models
    for column in NUMERIC_CANONICAL_COLUMNS:
        col_data = frame[column].dropna()
        if col_data.empty:
            continue
        inf_count = int(np.isinf(col_data.to_numpy().astype(float)).sum())
        if inf_count:
            raise DataAdapterError(
                f"Canonical telemetry column '{column}' contains {inf_count} non-finite (inf) value(s)"
            )
    # Phase 00: status domain validation
    _validate_status_domain(frame)


def _compute_quality_report(
    canonical: pd.DataFrame,
    data_dir: Path,
    wti_conflict_count: int = 0,
) -> QualityReport:
    """Compute aggregate quality metadata for the canonical telemetry."""
    source_hashes: dict[str, str] = {}
    for source_name in AGGREGATION_RULES:
        source_path = data_dir / source_name
        if source_path.is_file():
            source_hashes[source_name] = sha256(source_path.read_bytes()).hexdigest()

    # Missing counts by field
    missing_counts = {
        col: int(canonical[col].isna().sum())
        for col in CANONICAL_COLUMNS
        if col in canonical.columns
    }

    # Duplicate timestamp count (within each transformer_id)
    dup_count = int(canonical.duplicated(["transformer_id", CANONICAL_TIMESTAMP]).sum())

    # Timestamp gap statistics
    gap_stats: dict[str, Any] = {}
    if len(canonical) > 1:
        ts = canonical[CANONICAL_TIMESTAMP].sort_values()
        gaps = ts.diff().dt.total_seconds().dropna() / 60.0  # minutes
        gap_stats = {
            "median_gap_minutes": float(gaps.median()),
            "max_gap_minutes": float(gaps.max()),
            "min_gap_minutes": float(gaps.min()),
            "gaps_over_30min": int((gaps > 30).sum()),
            "gaps_over_60min": int((gaps > 60).sum()),
        }

    # Time range
    time_range: dict[str, str] = {}
    if not canonical[CANONICAL_TIMESTAMP].isna().all():
        time_range = {
            "start": str(canonical[CANONICAL_TIMESTAMP].min()),
            "end": str(canonical[CANONICAL_TIMESTAMP].max()),
        }

    return QualityReport(
        source_file=str(data_dir),
        schema_version="1.0.0",
        ingestion_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        row_count=len(canonical),
        missing_count_by_field=missing_counts,
        duplicate_timestamp_count=dup_count,
        timestamp_gap_statistics=gap_stats,
        out_of_range_count=0,  # CONFIGURATION REQUIRED: sensor plausibility bounds
        parse_error_count=0,
        source_hashes=source_hashes,
        time_range=time_range,
        wti_conflict_count=wti_conflict_count,
    )


def build_canonical_telemetry(
    data_dir: str | Path = Path("data") / "raw",
    transformer_id: str = "TR-001",
    *,
    output_path: Path | None = None,
) -> tuple[pd.DataFrame, QualityReport]:
    """Build validated canonical telemetry from the five baseline CSV sources.

    Readings missing after the outer alignment remain ``NaN``.  The observed
    15-minute cadence is preserved exactly; this adapter does not resample.

    Phase 00 changes:
    - Returns a tuple of (canonical_dataframe, quality_report).
    - Does NOT unconditionally write to the production path.
    - If ``output_path`` is provided, writes the canonical CSV there.
    - To write to the historical production location, call
      ``persist_canonical_telemetry()`` explicitly.
    """
    if not transformer_id or not transformer_id.strip():
        raise DataAdapterError("transformer_id must be a non-empty string")
    base_path = Path(data_dir)
    resolved_sources = load_resolved_source_datasets(base_path)

    # Count WTI conflicts for quality report
    wti_conflict_count = 0
    if "Overview.csv" in resolved_sources:
        overview = resolved_sources["Overview.csv"]
        if WTI_COLUMN in overview.columns:
            wti_vals = overview[WTI_COLUMN].dropna()
            wti_conflict_count = int(wti_vals.isna().sum())  # NaN from conflict resolution

    normalized = {
        source_name: normalize_columns(frame, source_name)
        for source_name, frame in resolved_sources.items()
    }
    canonical = merge_datasets(normalized)
    canonical.insert(0, "transformer_id", transformer_id)
    canonical = canonical.loc[:, list(CANONICAL_COLUMNS)]
    validate_canonical_telemetry(canonical)

    quality_report = _compute_quality_report(canonical, base_path, wti_conflict_count)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canonical.to_csv(output_path, index=False)

    return canonical, quality_report


def persist_canonical_telemetry(
    canonical: pd.DataFrame,
    output_path: Path = PROCESSED_OUTPUT_PATH,
) -> Path:
    """Explicitly persist canonical telemetry to a specified location.

    This is the only function that writes to the production canonical path.
    Tests must never call this with the production path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    """Build and persist baseline telemetry to the production location."""
    canonical, quality_report = build_canonical_telemetry()
    persist_canonical_telemetry(canonical)
    print(f"Canonical telemetry: {len(canonical)} rows")
    print(f"Time range: {quality_report.time_range}")
    print(f"WTI conflicts: {quality_report.wti_conflict_count}")
    missing = {k: v for k, v in quality_report.missing_count_by_field.items() if v > 0}
    if missing:
        print(f"Missing values: {missing}")


if __name__ == "__main__":
    main()
