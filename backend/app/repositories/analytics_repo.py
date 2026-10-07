from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.repositories.query_helpers import aggregate_signals, page_rows, window_statement
from app.schemas.analytics import MLResultIn


def get_for_telemetry(session: Session, telemetry_id: int) -> Analytics | None:
    return session.scalar(select(Analytics).where(Analytics.telemetry_id == telemetry_id))


def insert_analytics(
    session: Session,
    telemetry_id: int,
    result: MLResultIn,
) -> tuple[Analytics, bool]:
    statement = (
        insert(Analytics)
        .values(
            telemetry_id=telemetry_id,
            **result.model_dump(mode="python"),
        )
        .on_conflict_do_nothing(index_elements=[Analytics.telemetry_id])
        .returning(Analytics)
    )
    row = session.scalar(statement)
    if row is not None:
        return row, True
    row = get_for_telemetry(session, telemetry_id)
    if row is None:
        raise RuntimeError("Analytics lookup did not return a row")
    return row, False


def read_window(
    session: Session,
    transformer_id: str,
    start: datetime,
    end: datetime,
    limit: int,
    offset: int,
    order: str,
) -> tuple[list[Analytics], int]:
    return page_rows(
        session,
        window_statement(Analytics, transformer_id, start, end),
        Analytics,
        limit,
        offset,
        order,
    )


def read_buckets(
    session: Session,
    transformer_id: str,
    start: datetime,
    end: datetime,
    signals: list[str],
    seconds: int,
) -> dict[str, dict[datetime, dict[str, Any]]]:
    return aggregate_signals(session, Analytics, transformer_id, start, end, signals, seconds)


def insert_many(session: Session, values: list[dict[str, Any]]) -> dict[int, Analytics]:
    if not values:
        return {}
    return {
        row.telemetry_id: row
        for row in session.scalars(
            insert(Analytics)
            .on_conflict_do_nothing(index_elements=[Analytics.telemetry_id])
            .returning(Analytics),
            values,
            execution_options={"render_nulls": True},
        )
    }
