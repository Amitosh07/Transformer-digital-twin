"""Indexed, read-only maintenance queries."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.maintenance_record import MaintenanceRecord
from app.repositories.query_helpers import page_rows, window_statement


def read_window(
    session: Session,
    asset: str,
    start: datetime,
    end: datetime,
    limit: int,
    offset: int,
    status: str | None,
) -> tuple[list[MaintenanceRecord], int]:
    statement = window_statement(MaintenanceRecord, asset, start, end)
    if status is not None:
        statement = statement.where(MaintenanceRecord.status == status)
    return page_rows(session, statement, MaintenanceRecord, limit, offset)
