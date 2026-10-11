from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.telemetry import Telemetry
from app.repositories.query_helpers import aggregate_signals, page_rows, window_statement
from app.schemas.telemetry import TelemetryIn
from app.services.semantic_payload import digest, canonical


class SemanticConflict(ValueError):
    reason = 'SEMANTIC_PAYLOAD_CONFLICT'
    def __init__(self, record, accepted_hash):
        self.record = record
        self.accepted_hash = accepted_hash
        super().__init__(self.reason)


def as_input(row: Telemetry) -> TelemetryIn:
    if row.semantic_payload:
        from ml.pipeline.identity import parse_record_json
        raw = parse_record_json(row.semantic_payload)
        raw['schema_version'] = row.schema_version
        if raw.get('acquisition') is not None:
            raw['acquisition']['snapshot_id'] = row.payload_hash
        return TelemetryIn.model_validate(raw)
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
    values['schema_version'] = record.schema_version
    values['acquisition'] = record.acquisition.model_dump(mode='json') if record.acquisition else None
    values['payload_hash'] = digest(record)
    values['semantic_payload'] = canonical(record)
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
    accepted_hash = row.payload_hash or digest(as_input(row))
    if accepted_hash != digest(record):
        raise SemanticConflict(record, accepted_hash)
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
            or_(Telemetry.ingestion_outcome == 'ACCEPTED', Telemetry.ingestion_outcome.is_(None)),
        )
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
    ).all()
    # One hour plus the preceding boundary; a dense stream is capped by limit.
    from datetime import timedelta
    start = before - timedelta(hours=1)
    ordered = list(reversed(rows))
    boundary = [row for row in ordered if row.timestamp < start]
    selected = boundary[-1:] + [row for row in ordered if row.timestamp >= start]
    return [as_input(row) for row in selected]


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
            or_(Telemetry.ingestion_outcome == 'ACCEPTED', Telemetry.ingestion_outcome.is_(None)),
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


def get_latest(session: Session, transformer_id: str) -> Telemetry | None:
    return session.scalar(
        select(Telemetry)
        .where(Telemetry.transformer_id == transformer_id)
        .order_by(Telemetry.timestamp.desc(), Telemetry.id.desc())
        .limit(1)
    )


def read_window_statement(transformer_id: str, start: datetime, end: datetime) -> Select:
    return window_statement(Telemetry, transformer_id, start, end)


def read_window(
    session: Session,
    transformer_id: str,
    start: datetime,
    end: datetime,
    limit: int,
    offset: int,
    order: str,
) -> tuple[list[Telemetry], int]:
    return page_rows(
        session, read_window_statement(transformer_id, start, end), Telemetry, limit, offset, order
    )


def read_buckets(
    session: Session,
    transformer_id: str,
    start: datetime,
    end: datetime,
    signals: list[str],
    seconds: int,
) -> dict[str, dict[datetime, dict[str, Any]]]:
    return aggregate_signals(session, Telemetry, transformer_id, start, end, signals, seconds)


def protection_events(
    session: Session, transformer_id: str, start: datetime, end: datetime
) -> list[Telemetry]:
    statement = read_window_statement(transformer_id, start, end).where(
        or_(
            Telemetry.oil_temp_alarm == 1,
            Telemetry.oil_temp_trip == 1,
            Telemetry.magnetic_oil_gauge_alarm == 1,
        )
    )
    return list(session.scalars(statement.order_by(Telemetry.timestamp, Telemetry.id).limit(500)))


def scenarios(session: Session, limit: int, offset: int) -> tuple[list[Any], int]:
    groups = select(
        Telemetry.scenario_id,
        func.min(Telemetry.timestamp).label("first_timestamp"),
        func.max(Telemetry.timestamp).label("last_timestamp"),
        func.count().label("row_count"),
    ).where(Telemetry.scenario_id.is_not(None))
    groups = groups.group_by(Telemetry.scenario_id)
    total = session.scalar(select(func.count()).select_from(groups.subquery())) or 0
    rows = session.execute(
        groups.order_by(Telemetry.scenario_id).limit(limit).offset(offset)
    ).mappings()
    return list(rows), total


def existing_keys(session: Session, records: list[TelemetryIn]) -> set[tuple[str, datetime]]:
    keys = list({(record.transformer_id, record.timestamp) for record in records})
    return set(
        session.execute(
            select(Telemetry.transformer_id, Telemetry.timestamp).where(
                tuple_(Telemetry.transformer_id, Telemetry.timestamp).in_(keys)
            )
        )
    )


def insert_many(
    session: Session, values: list[dict[str, Any]]
) -> dict[tuple[str, datetime], Telemetry]:
    if not values:
        return {}
    rows = session.scalars(
        insert(Telemetry)
        .on_conflict_do_nothing(index_elements=[Telemetry.transformer_id, Telemetry.timestamp])
        .returning(Telemetry),
        values,
        execution_options={"render_nulls": True},
    )
    return {(row.transformer_id, row.timestamp): row for row in rows}
