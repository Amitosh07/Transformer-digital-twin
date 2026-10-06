from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryIn


def as_input(row: Telemetry) -> TelemetryIn:
    return TelemetryIn.model_validate(
        {field: getattr(row, field) for field in TelemetryIn.model_fields}
    )


def insert_telemetry(
    session: Session,
    record: TelemetryIn,
    *,
    schema_version: str,
    is_missing_critical: bool,
    data_quality_score: float,
) -> tuple[Telemetry, bool]:
    values = record.model_dump(mode="python") | {
        "schema_version": schema_version,
        "is_missing_critical": is_missing_critical,
        "data_quality_score": data_quality_score,
    }
    statement = (
        insert(Telemetry)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[Telemetry.transformer_id, Telemetry.timestamp],
        )
        .returning(Telemetry)
    )
    row = session.scalar(statement)
    if row is not None:
        return row, False
    row = session.scalar(
        select(Telemetry).where(
            Telemetry.transformer_id == record.transformer_id,
            Telemetry.timestamp == record.timestamp,
        )
    )
    if row is None:
        raise RuntimeError("Duplicate telemetry lookup did not return a row")
    return row, True


def load_history(
    session: Session,
    transformer_id: str,
    before: datetime,
    limit: int,
) -> list[TelemetryIn]:
    rows = session.scalars(
        select(Telemetry)
        .where(
            Telemetry.transformer_id == transformer_id,
            Telemetry.timestamp < before,
        )
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
    ).all()
    return [as_input(row) for row in reversed(rows)]


def load_batch_history(
    session: Session,
    transformer_id: str,
    first: datetime,
    last: datetime,
    limit: int,
) -> list[TelemetryIn]:
    # One query includes the initial window and existing rows interleaved with this batch.
    initial_ids = (
        select(Telemetry.id)
        .where(
            Telemetry.transformer_id == transformer_id,
            Telemetry.timestamp < first,
        )
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
    )
    rows = session.scalars(
        select(Telemetry)
        .where(
            Telemetry.transformer_id == transformer_id,
            Telemetry.timestamp < last,
            or_(Telemetry.id.in_(initial_ids), Telemetry.timestamp >= first),
        )
        .order_by(Telemetry.timestamp)
    ).all()
    return [as_input(row) for row in rows]


def load_stored_window(
    session: Session,
    start: datetime,
    end: datetime,
    transformer_id: str | None,
) -> list[TelemetryIn]:
    statement = select(Telemetry).where(Telemetry.timestamp >= start, Telemetry.timestamp <= end)
    if transformer_id is not None:
        statement = statement.where(Telemetry.transformer_id == transformer_id)
    return [
        as_input(row)
        for row in session.scalars(
            statement.order_by(Telemetry.timestamp, Telemetry.transformer_id),
        )
    ]
