from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.v1.query_dependencies import OrderQuery, PageQuery, WindowQuery
from app.api.v1.read_examples import (
    ANALYTIC_POINT,
    HEALTH,
    SCENARIO,
    TELEMETRY_POINT,
    TREND,
    page_example,
    response_example,
)
from app.db.session import DatabaseSession
from app.schemas.common import Page
from app.schemas.query import AnalyticsPoint, HealthPoint, ScenarioOut, TelemetryPoint, TrendOut
from app.services import query_service, trend_service

router = APIRouter()


@router.get(
    "/transformers/{id}/telemetry",
    response_model=Page[TelemetryPoint],
    tags=["telemetry"],
    response_model_exclude_unset=True,
    description=(
        "Bounded canonical telemetry page. fields projects an allowlist; "
        "timestamp remains included."
    ),
    responses=response_example(page_example(TELEMETRY_POINT)),
)
def get_telemetry(
    id: str,
    db: DatabaseSession,
    time: WindowQuery,
    page: PageQuery,
    order: OrderQuery = "asc",
    fields: Annotated[str | None, Query()] = None,
) -> Page[TelemetryPoint]:
    return query_service.telemetry(db, id, time, page, order, fields)


@router.get(
    "/transformers/{id}/health",
    response_model=Page[HealthPoint],
    tags=["health"],
    responses=response_example(page_example(HEALTH)),
)
def get_health(
    id: str, db: DatabaseSession, time: WindowQuery, page: PageQuery, order: OrderQuery = "asc"
) -> Page[HealthPoint]:
    return query_service.health(db, id, time, page, order)


@router.get(
    "/transformers/{id}/analytics",
    response_model=Page[AnalyticsPoint],
    tags=["analytics"],
    description="Bounded analytic series; fault_risk/predicted_fault describe proxy risk.",
    responses=response_example(page_example(ANALYTIC_POINT)),
)
def get_analytics(
    id: str, db: DatabaseSession, time: WindowQuery, page: PageQuery, order: OrderQuery = "asc"
) -> Page[AnalyticsPoint]:
    return query_service.analytics(db, id, time, page, order)


@router.get(
    "/transformers/{id}/trends",
    response_model=TrendOut,
    tags=["trends"],
    description=(
        "SQL buckets with explicit null gaps, no interpolation. Fault signals describe proxy risk."
    ),
    responses=response_example(TREND),
)
def get_trends(
    id: str,
    db: DatabaseSession,
    time: WindowQuery,
    signals: Annotated[str, Query()],
    window: Annotated[Literal["1h", "6h", "24h", "7d"], Query()] = "24h",
) -> TrendOut:
    return trend_service.trends(db, id, signals, window, time)


@router.get(
    "/scenarios",
    response_model=Page[ScenarioOut],
    tags=["scenarios"],
    description="All-time distinct scenario metadata, bounded by limit/offset.",
    responses=response_example(page_example(SCENARIO)),
)
def get_scenarios(db: DatabaseSession, page: PageQuery) -> Page[ScenarioOut]:
    return query_service.scenarios(db, page)
