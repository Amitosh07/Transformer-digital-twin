"""Per-run validation and completeness statistics; source values are never imputed."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from statistics import median
from typing import Any

from pydantic import ValidationError

from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS
from app.schemas.ingestion import IngestionSummary, ValidationSample
from app.schemas.telemetry import TelemetryIn

RANGE_FIELDS = {
    "power_factor_l1",
    "power_factor_l2",
    "power_factor_l3",
    "oil_temp_alarm",
    "oil_temp_trip",
    "magnetic_oil_gauge_alarm",
}


@dataclass
class QualityStats:
    row_count: int
    inserted_count: int = 0
    duplicate_count: int = 0
    parse_error_count: int = 0
    out_of_range_count: int = 0
    missing_count_by_field: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CANONICAL_TELEMETRY_FIELDS, 0),
    )
    timestamps: dict[str, set[datetime]] = field(default_factory=lambda: defaultdict(set))
    errors_sample: list[ValidationSample] = field(default_factory=list)

    def parsed(self, record: TelemetryIn) -> None:
        for name in CANONICAL_TELEMETRY_FIELDS:
            if getattr(record, name) is None:
                self.missing_count_by_field[name] += 1
        self.timestamps[record.transformer_id].add(record.timestamp)

    def rejected(self, index: int, error: ValidationError) -> None:
        errors = error.errors(include_input=True, include_context=False)
        is_range = all(
            item["loc"]
            and item["loc"][0] in RANGE_FIELDS
            and item["type"] != "finite_number"
            and not (isinstance(item.get("input"), float) and not isfinite(item["input"]))
            for item in errors
        )
        if is_range:
            self.out_of_range_count += 1
        else:
            self.parse_error_count += 1
        if len(self.errors_sample) < 20:
            item = errors[0]
            self.errors_sample.append(
                ValidationSample(
                    row_index=index,
                    field=str(item["loc"][0]) if item["loc"] else "record",
                    message=item["msg"],
                )
            )

    def gap_stats(self) -> dict[str, float | int | None]:
        gaps: list[float] = []
        for timestamps in self.timestamps.values():
            ordered = sorted(timestamps)
            gaps.extend(
                (right - left).total_seconds()
                for left, right in zip(ordered, ordered[1:], strict=False)
            )
        return {
            "min_s": min(gaps) if gaps else None,
            "median_s": median(gaps) if gaps else None,
            "max_s": max(gaps) if gaps else None,
            "count": len(gaps),
        }

    def values(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "inserted_count": self.inserted_count,
            "duplicate_count": self.duplicate_count,
            "parse_error_count": self.parse_error_count,
            "out_of_range_count": self.out_of_range_count,
            "missing_count_by_field": dict(self.missing_count_by_field),
            "timestamp_gap_stats": self.gap_stats(),
        }

    def summary(self, run_id: int) -> IngestionSummary:
        counts = self.values()
        return IngestionSummary(
            run_id=run_id,
            errors_sample=self.errors_sample,
            **{
                key: value
                for key, value in counts.items()
                if key not in {"missing_count_by_field", "timestamp_gap_stats"}
            },
        )


def parse_records(
    rows: list[dict[str, Any]],
    source_name: str,
    *,
    transformer_id: str | None = None,
    force_source: bool = False,
) -> tuple[list[TelemetryIn], QualityStats]:
    stats = QualityStats(row_count=len(rows))
    records: list[TelemetryIn] = []
    for index, row in enumerate(rows):
        payload = dict(row)
        payload["source_name"] = (
            source_name if force_source else payload.get("source_name") or source_name
        )
        if transformer_id is not None:
            payload["transformer_id"] = transformer_id
        try:
            record = TelemetryIn.model_validate(payload)
        except ValidationError as exc:
            stats.rejected(index, exc)
            continue
        records.append(record)
        stats.parsed(record)
    return records, stats
