"""Convert the five baseline source CSVs into canonical transformer telemetry.

This module is deliberately the only ML-layer location that knows the public
dataset's filenames and raw column names.  It preserves the supplied timestamp
cadence; it does not resample or impute readings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Literal, Mapping

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype


TIMESTAMP_COLUMN: Final = "DeviceTimeStamp"
CANONICAL_TIMESTAMP: Final = "timestamp"
EXCLUDED_CURRENT_VOLTAGE_COLUMNS: Final = ("VL12", "VL23", "VL31")

# The semantic treatment of every field read from each source is explicit.  In
# particular, counters are never summed/averaged and protection states retain
# an active state found in any duplicate source row.
AGGREGATION_RULES: Final[dict[str, dict[Literal["mean", "max", "first"], tuple[str, ...]]]] = {
    "CurrentVoltage.csv": {
        "mean": ("VL1", "VL2", "VL3", "IL1", "IL2", "IL3", "INUT"),
        "max": (),
        "first": (),
    },
    "Overview.csv": {
        "mean": ("OTI", "WTI", "ATI", "OLI"),
        "max": ("OTI_A", "OTI_T", "MOG_A"),
        "first": (),
    },
    "Power.csv": {
        "mean": ("WL1", "WL2", "WL3", "VAL1", "VAL2", "VAL3", "RVAL1", "RVAL2", "RVAL3"),
        "max": (),
        "first": (),
    },
    "PowerFactor.csv": {
        "mean": (
            "PFL1", "PFL2", "PFL3", "Avg_PF", "Sum_PF", "FRQ", "THDVL1", "THDVL2",
            "THDVL3", "THDIL1", "THDIL2", "THDIL3", "MDIL1", "MDIL2", "MDIL3",
        ),
        "max": (),
        "first": (),
    },
    "TotalPower.csv": {
        "mean": ("KW", "KVA", "KVAR", "MPD", "MKVAD"),
        "max": (),
        "first": ("KWH", "KWH_I", "KVARH"),
    },
}

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


class DataAdapterError(ValueError):
    """Raised when a source file or canonical telemetry fails validation."""


@dataclass(frozen=True)
class ValidationReport:
    """A compact, serialisable report for a validated canonical DataFrame."""

    row_count: int
    column_count: int
    min_timestamp: pd.Timestamp | None
    max_timestamp: pd.Timestamp | None
    missing_values_by_column: dict[str, int]
    missing_values_total: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _source_columns(source_name: str) -> tuple[str, ...]:
    rules = AGGREGATION_RULES[source_name]
    return tuple(column for fields in rules.values() for column in fields)


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


def resolve_duplicates(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Aggregate duplicate timestamps with the source's explicit field rules."""
    rules = AGGREGATION_RULES[source_name]
    result = frame.sort_values(TIMESTAMP_COLUMN, kind="stable").copy()
    aggregation = {column: method for method, columns in rules.items() for column in columns}
    # Convert raw telemetry deliberately: unexpected non-numeric source values are a
    # data-quality failure, not something the adapter should silently coerce.
    for column in aggregation:
        result[column] = pd.to_numeric(result[column], errors="raise")
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


def validate_canonical_telemetry(frame: pd.DataFrame) -> ValidationReport:
    """Validate the canonical boundary and return its missing-reading report."""
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
    if not frame[CANONICAL_TIMESTAMP].is_monotonic_increasing:
        raise DataAdapterError("Canonical telemetry is not sorted by timestamp")
    if frame[CANONICAL_TIMESTAMP].duplicated().any():
        raise DataAdapterError("Canonical telemetry contains duplicate timestamps after resolution")
    if frame["transformer_id"].isna().any() or (frame["transformer_id"].astype(str).str.strip() == "").any():
        raise DataAdapterError("Canonical transformer_id must be populated for every row")
    non_numeric = [column for column in NUMERIC_CANONICAL_COLUMNS if not is_numeric_dtype(frame[column])]
    if non_numeric:
        raise DataAdapterError(f"Canonical telemetry columns must be numeric: {non_numeric}")
    missing_by_column = {column: int(count) for column, count in frame.isna().sum().items() if count}
    return ValidationReport(
        row_count=len(frame),
        column_count=len(frame.columns),
        min_timestamp=frame[CANONICAL_TIMESTAMP].min() if not frame.empty else None,
        max_timestamp=frame[CANONICAL_TIMESTAMP].max() if not frame.empty else None,
        missing_values_by_column=missing_by_column,
        missing_values_total=sum(missing_by_column.values()),
    )


def build_canonical_telemetry(
    data_dir: str | Path = Path("data") / "raw", transformer_id: str = "TR-001"
) -> pd.DataFrame:
    """Build validated canonical telemetry from the five baseline CSV sources.

    Readings missing after the outer alignment remain ``NaN``.  The observed
    15-minute cadence is preserved exactly; this adapter does not resample.
    The validation report is available at ``result.attrs['validation_report']``.
    """
    if not transformer_id or not transformer_id.strip():
        raise DataAdapterError("transformer_id must be a non-empty string")
    base_path = Path(data_dir)
    normalized: dict[str, pd.DataFrame] = {}
    for source_name in AGGREGATION_RULES:
        raw = load_dataset(base_path / source_name, source_name)
        normalized[source_name] = normalize_columns(
            resolve_duplicates(parse_timestamp(raw, source_name), source_name), source_name
        )
    canonical = merge_datasets(normalized)
    canonical.insert(0, "transformer_id", transformer_id)
    canonical = canonical.loc[:, CANONICAL_COLUMNS]
    report = validate_canonical_telemetry(canonical)
    canonical.attrs["validation_report"] = report.to_dict()
    return canonical


def main() -> None:
    """Build baseline telemetry and print its compact validation summary."""
    telemetry = build_canonical_telemetry()
    print(telemetry.attrs["validation_report"])


if __name__ == "__main__":
    main()
