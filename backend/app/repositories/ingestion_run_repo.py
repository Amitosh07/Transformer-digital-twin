from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.ingestion_run import IngestionRun

RunStatus = Literal["RUNNING", "COMPLETED", "FAILED"]


def create_run(
    session: Session, source_name: str, schema_version: str, row_count: int
) -> IngestionRun:
    row = IngestionRun(
        source_name=source_name,
        schema_version=schema_version,
        status="RUNNING",
        row_count=row_count,
    )
    session.add(row)
    session.flush()
    return row


def get_run(session: Session, run_id: int) -> IngestionRun | None:
    return session.get(IngestionRun, run_id)


def update_run(
    session: Session,
    run_id: int,
    values: dict[str, Any],
    status: RunStatus,
) -> IngestionRun:
    row = get_run(session, run_id)
    if row is None:
        raise LookupError("Ingestion run was not found")
    for field, value in values.items():
        setattr(row, field, value)
    row.status = status
    if status != "RUNNING":
        row.finished_at = datetime.now(UTC)
    session.flush()
    return row
