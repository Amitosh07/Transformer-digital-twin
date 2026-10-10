"""Dashboard query orchestration; routes contain no business logic."""

from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.core.config import get_settings
from app.models.transformer import Transformer
from app.repositories import (
    alert_repo,
    analytics_repo,
    maintenance_repo,
    telemetry_repo,
    transformer_repo,
)
from app.schemas.alert import AlertOut
from app.schemas.analytics import AnalyticsOut
from app.schemas.common import Page
from app.schemas.maintenance import MaintenanceOut
from app.schemas.query import (
    TELEMETRY_FIELDS,
    AnalyticsPoint,
    DataSource,
    HealthPoint,
    Pagination,
    ResolvedWindow,
    ScenarioOut,
    TelemetryPoint,
    TimeWindow,
)
from app.schemas.state import LatestStateOut
from app.schemas.telemetry import TelemetryOut
from app.schemas.transformer import TransformerIn, TransformerOut, TransformerPatch
from app.services.demo_mode import is_demo_mode

T = TypeVar("T", bound=BaseModel)


def query_error(field: str, message: str) -> None:
    raise RequestValidationError([{"loc": ("query", field), "msg": message, "type": "value_error"}])


def require_transformer(session: Session, asset: str) -> Transformer:
    row = transformer_repo.get(session, asset)
    if row is None:
        raise HTTPException(404, "Transformer not found")
    return row


def resolve_window(
    session: Session, asset: str, window: TimeWindow, duration: timedelta | None = None
) -> ResolvedWindow:
    settings = get_settings()
    end = window.to_time
    if end is None:
        latest = (
            telemetry_repo.get_latest(session, asset)
            if (window.anchor == "latest" and window.from_time is None)
            else None
        )
        end = latest.timestamp if latest is not None else datetime.now(UTC)
    start = window.from_time or end - (duration or timedelta(hours=settings.default_window_hours))
    if start >= end:
        query_error("from", "from must be earlier than to")
    if end - start > timedelta(days=settings.max_window_days):
        query_error("from", f"Window exceeds MAX_WINDOW_DAYS={settings.max_window_days}")
    return ResolvedWindow(start=start, end=end)


def select_names(
    value: str, allowed: list[str], field: str, maximum: int | None = None
) -> list[str]:
    names = [name.strip() for name in value.split(",")]
    if not names or any(name not in allowed for name in names):
        query_error(field, "Unknown or empty selection. Allowed names: " + ", ".join(allowed))
    if maximum is not None and len(names) > maximum:
        query_error(field, f"At most {maximum} signals are allowed")
    return list(dict.fromkeys(names))


def _page(model: type[T], rows: list[Any], total: int, pagination: Pagination) -> Page[T]:
    return Page[model](
        items=[model.model_validate(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def transformers(session: Session, pagination: Pagination) -> Page[TransformerOut]:
    rows, total = transformer_repo.read_page(session, pagination.limit, pagination.offset)
    return _page(TransformerOut, rows, total, pagination)


def transformer(session: Session, asset: str) -> TransformerOut:
    return TransformerOut.model_validate(require_transformer(session, asset))


def create_transformer(session: Session, payload: TransformerIn) -> TransformerOut:
    row = transformer_repo.create(session, payload)
    if row is None:
        session.rollback()
        raise HTTPException(409, "Transformer already exists")
    result = TransformerOut.model_validate(row)
    session.commit()
    return result


def patch_transformer(session: Session, asset: str, payload: TransformerPatch) -> TransformerOut:
    row = require_transformer(session, asset)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise RequestValidationError(
            [{"loc": ("body", "name"), "msg": "name cannot be null", "type": "value_error"}]
        )
    result = TransformerOut.model_validate(transformer_repo.patch(session, row, changes))
    session.commit()
    return result


def latest(session: Session, asset: str) -> LatestStateOut:
    transformer_out = transformer(session, asset)
    row = telemetry_repo.get_latest(session, asset)
    telemetry = TelemetryOut.model_validate(row) if row is not None else None
    analytic_row = analytics_repo.get_for_telemetry(session, row.id) if row is not None else None
    analytics = AnalyticsOut.model_validate(analytic_row) if analytic_row is not None else None
    if analytics is not None and analytics.error_detail not in (
        None,
        "ML analysis failed",
        "ML analysis timed out",
    ):
        analytics.error_detail = "ML analysis failed"
    source = (
        DataSource(source_name=telemetry.source_name, scenario_id=telemetry.scenario_id)
        if (telemetry is not None)
        else DataSource()
    )
    return LatestStateOut(
        transformer=transformer_out,
        telemetry=telemetry,
        analytics=analytics,
        open_alerts_count=alert_repo.count_open(session, asset),
        demo_mode=is_demo_mode(source.source_name, source.scenario_id),
        data_source=source,
        schema_version=analytics.schema_version
        if analytics
        else (telemetry.schema_version if telemetry else get_settings().schema_version),
        feature_version=analytics.feature_version if analytics else None,
        model_version=analytics.model_version if analytics else None,
    )


def telemetry(
    session: Session,
    asset: str,
    window: TimeWindow,
    pagination: Pagination,
    order: str,
    fields: str | None,
) -> Page[TelemetryPoint]:
    require_transformer(session, asset)
    names = select_names(fields, TELEMETRY_FIELDS, "fields") if fields is not None else None
    resolved = resolve_window(session, asset, window)
    rows, total = telemetry_repo.read_window(
        session, asset, resolved.start, resolved.end, pagination.limit, pagination.offset, order
    )
    points = []
    for row in rows:
        values = TelemetryOut.model_validate(row).model_dump()
        if names is not None:
            values = {name: values[name] for name in set(names) | {"timestamp"}}
        points.append(TelemetryPoint.model_validate(values))
    return Page[TelemetryPoint](
        items=points, total=total, limit=pagination.limit, offset=pagination.offset
    )


def health(
    session: Session, asset: str, window: TimeWindow, pagination: Pagination, order: str
) -> Page[HealthPoint]:
    require_transformer(session, asset)
    resolved = resolve_window(session, asset, window)
    rows, total = analytics_repo.read_window(
        session, asset, resolved.start, resolved.end, pagination.limit, pagination.offset, order
    )
    return _page(HealthPoint, rows, total, pagination)


def analytics(
    session: Session, asset: str, window: TimeWindow, pagination: Pagination, order: str
) -> Page[AnalyticsPoint]:
    require_transformer(session, asset)
    resolved = resolve_window(session, asset, window)
    rows, total = analytics_repo.read_window(
        session, asset, resolved.start, resolved.end, pagination.limit, pagination.offset, order
    )
    return _page(AnalyticsPoint, rows, total, pagination)


def alerts(
    session: Session,
    asset: str,
    window: TimeWindow,
    pagination: Pagination,
    severity: str | None,
    status: str | None,
) -> Page[AlertOut]:
    require_transformer(session, asset)
    resolved = resolve_window(session, asset, window)
    rows, total = alert_repo.read_window(
        session,
        asset,
        resolved.start,
        resolved.end,
        pagination.limit,
        pagination.offset,
        severity,
        status,
    )
    return _page(AlertOut, rows, total, pagination)


def maintenance(
    session: Session, asset: str, window: TimeWindow, pagination: Pagination, status: str | None
) -> Page[MaintenanceOut]:
    require_transformer(session, asset)
    resolved = resolve_window(session, asset, window)
    rows, total = maintenance_repo.read_window(
        session, asset, resolved.start, resolved.end, pagination.limit, pagination.offset, status
    )
    return _page(MaintenanceOut, rows, total, pagination)


def scenarios(session: Session, pagination: Pagination) -> Page[ScenarioOut]:
    rows, total = telemetry_repo.scenarios(session, pagination.limit, pagination.offset)
    return _page(ScenarioOut, rows, total, pagination)
