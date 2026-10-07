"""Indexed alert queries and transactional lifecycle persistence."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.repositories.query_helpers import page_rows, window_statement


def count_open(session: Session, asset: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.transformer_id == asset, Alert.status == "OPEN")
        )
        or 0
    )


def read_window(
    session: Session,
    asset: str,
    start: datetime,
    end: datetime,
    limit: int,
    offset: int,
    severity: str | None,
    status: str | None,
) -> tuple[list[Alert], int]:
    statement = window_statement(Alert, asset, start, end)
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if status is not None:
        statement = statement.where(Alert.status == status)
    return page_rows(session, statement, Alert, limit, offset)


def get(session: Session, alert_id: int, *, lock: bool = False) -> Alert | None:
    statement = select(Alert).where(Alert.id == alert_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalar(statement)


def active(session: Session, asset: str) -> list[Alert]:
    cache = session.info.get("ingestion_lifecycle_cache")
    if cache is not None:
        return [row for row in cache.alerts[asset] if row.status in ("OPEN", "ACKNOWLEDGED")]
    return list(
        session.scalars(
            select(Alert)
            .where(Alert.transformer_id == asset, Alert.status.in_(["OPEN", "ACKNOWLEDGED"]))
            .order_by(Alert.alert_type, Alert.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def insert_active(session: Session, values: dict[str, Any]) -> Alert:
    cache = session.info.get("ingestion_lifecycle_cache")
    if cache is not None:
        row = Alert(**values)
        cache.alerts[row.transformer_id].append(row)
        cache.new_alerts.append(row)
        return row
    row = session.scalar(
        insert(Alert)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[Alert.transformer_id, Alert.alert_type],
            index_where=text("status IN ('OPEN','ACKNOWLEDGED')"),
        )
        .returning(Alert)
    )
    if row is not None:
        return row
    row = session.scalar(
        select(Alert)
        .where(
            Alert.transformer_id == values["transformer_id"],
            Alert.alert_type == values["alert_type"],
            Alert.status.in_(["OPEN", "ACKNOWLEDGED"]),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise RuntimeError("Active alert conflict lookup failed")
    return row
