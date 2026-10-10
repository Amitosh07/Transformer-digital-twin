"""Indexed time predicates, deterministic paging and SQL trend aggregation."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def window_statement(model: Any, asset: str, start: datetime, end: datetime) -> Select:
    return select(model).where(
        model.transformer_id == asset, model.timestamp >= start, model.timestamp <= end
    )


def page_rows(
    session: Session, statement: Select, model: Any, limit: int, offset: int, order: str = "asc"
) -> tuple[list[Any], int]:
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    ordering = (
        (model.timestamp.desc(), model.id.desc())
        if order == "desc"
        else (model.timestamp.asc(), model.id.asc())
    )
    rows = session.scalars(statement.order_by(*ordering).limit(limit).offset(offset)).all()
    return list(rows), total


def aggregate_signals(
    session: Session,
    model: Any,
    asset: str,
    start: datetime,
    end: datetime,
    signals: list[str],
    seconds: int,
) -> dict[str, dict[datetime, dict[str, Any]]]:
    if not signals:
        return {}
    bucket = func.date_bin(timedelta(seconds=seconds), model.timestamp, start)
    aggregates = [bucket.label("bucket_start")]
    for name in signals:
        column = getattr(model, name)
        aggregates.extend(
            [
                func.avg(column).label(name + "_avg"),
                func.min(column).label(name + "_min"),
                func.max(column).label(name + "_max"),
                func.count(column).label(name + "_count"),
            ]
        )
    rows = session.execute(
        select(*aggregates)
        .where(
            model.transformer_id == asset,
            model.timestamp >= start,
            model.timestamp <= end,
        )
        .group_by(bucket)
        .order_by(bucket)
    ).mappings()
    result: dict[str, dict[datetime, dict[str, Any]]] = {name: {} for name in signals}
    for row in rows:
        for name in signals:
            result[name][row["bucket_start"]] = {
                "bucket_start": row["bucket_start"],
                "avg": row[name + "_avg"],
                "min": row[name + "_min"],
                "max": row[name + "_max"],
                "count": row[name + "_count"],
            }
    return result
