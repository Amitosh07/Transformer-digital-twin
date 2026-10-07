"""Bounded SQL aggregates with explicit null gaps and protection events."""

from datetime import timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.repositories import analytics_repo, telemetry_repo
from app.schemas.query import (
    ANALYTIC_SIGNALS,
    TREND_SIGNALS,
    ProtectionEvent,
    TimeWindow,
    TrendBucket,
    TrendOut,
)
from app.services.query_service import require_transformer, resolve_window, select_names

WINDOWS: dict[str, tuple[timedelta, int]] = {
    "1h": (timedelta(hours=1), 15),
    "6h": (timedelta(hours=6), 120),
    "24h": (timedelta(hours=24), 300),
    "7d": (timedelta(days=7), 3600),
}


def trends(
    session: Session, asset: str, signals: str, window: str, time_window: TimeWindow
) -> TrendOut:
    require_transformer(session, asset)
    names = select_names(signals, TREND_SIGNALS, "signals", maximum=8)
    duration, base_seconds = WINDOWS[window]
    resolved = resolve_window(session, asset, time_window, duration)
    seconds = max(base_seconds, ceil((resolved.end - resolved.start).total_seconds() / 300))
    numeric = [name for name in names if name not in ANALYTIC_SIGNALS]
    analytic = [name for name in names if name in ANALYTIC_SIGNALS]
    aggregated = telemetry_repo.read_buckets(
        session, asset, resolved.start, resolved.end, numeric, seconds
    )
    aggregated.update(
        analytics_repo.read_buckets(session, asset, resolved.start, resolved.end, analytic, seconds)
    )
    starts = []
    cursor = resolved.start
    while cursor <= resolved.end:
        starts.append(cursor)
        cursor += timedelta(seconds=seconds)
    series = {
        name: [
            TrendBucket.model_validate(
                aggregated[name].get(
                    start,
                    {
                        "bucket_start": start,
                        "avg": None,
                        "min": None,
                        "max": None,
                        "count": 0,
                    },
                )
            )
            for start in starts
        ]
        for name in names
    }
    return TrendOut(
        start=resolved.start,
        end=resolved.end,
        bucket_seconds=seconds,
        signals=series,
        no_data_signals=[
            name for name, buckets in series.items() if not any(bucket.count for bucket in buckets)
        ],
        protection_events=[
            ProtectionEvent.model_validate(row)
            for row in telemetry_repo.protection_events(
                session, asset, resolved.start, resolved.end
            )
        ],
    )
