"""Indexed, read-only alert queries."""

from datetime import datetime

from sqlalchemy import func, select
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
