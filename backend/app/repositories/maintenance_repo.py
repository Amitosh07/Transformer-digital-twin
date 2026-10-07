"""Maintenance reads and persistence in the caller-owned transaction."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
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


def get(session: Session, record_id: int, *, lock: bool = False) -> MaintenanceRecord | None:
    statement = select(MaintenanceRecord).where(MaintenanceRecord.id == record_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalar(statement)


def open_records(session: Session, asset: str) -> list[MaintenanceRecord]:
    cache = session.info.get("ingestion_lifecycle_cache")
    if cache is not None:
        return [row for row in cache.maintenance[asset] if row.status == "OPEN"]
    return list(
        session.scalars(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.transformer_id == asset, MaintenanceRecord.status == "OPEN")
            .order_by(MaintenanceRecord.timestamp.desc(), MaintenanceRecord.id.desc())
            .with_for_update()
        )
    )


def insert_record(session: Session, values: dict[str, Any]) -> MaintenanceRecord:
    row = MaintenanceRecord(**values)
    cache = session.info.get("ingestion_lifecycle_cache")
    if cache is not None:
        cache.maintenance[row.transformer_id].append(row)
        cache.new_maintenance.append(row)
    else:
        session.add(row)
        session.flush()
    return row
