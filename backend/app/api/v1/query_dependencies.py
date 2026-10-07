"""Shared UTC window and configurable pagination dependencies."""

from typing import Annotated, Literal

from fastapi import Depends, Query

from app.core.config import get_settings
from app.schemas.common import UtcDatetime
from app.schemas.query import Pagination, TimeWindow
from app.services.query_service import query_error


def time_window(
    from_time: Annotated[
        UtcDatetime | None, Query(alias="from", description="ISO-8601 with offset")
    ] = None,
    to_time: Annotated[
        UtcDatetime | None, Query(alias="to", description="ISO-8601 with offset")
    ] = None,
    anchor: Annotated[
        Literal["latest", "now"],
        Query(description="With no from/to, latest ends at the asset's latest telemetry time."),
    ] = "now",
) -> TimeWindow:
    return TimeWindow(from_time=from_time, to_time=to_time, anchor=anchor)


def pagination(
    limit: Annotated[int, Query(gt=0, description="Default 500; capped by MAX_PAGE_LIMIT")] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    maximum = get_settings().max_page_limit
    if limit > maximum:
        query_error("limit", f"limit exceeds MAX_PAGE_LIMIT={maximum}")
    return Pagination(limit=limit, offset=offset)


WindowQuery = Annotated[TimeWindow, Depends(time_window)]
PageQuery = Annotated[Pagination, Depends(pagination)]
OrderQuery = Annotated[Literal["asc", "desc"], Query()]
