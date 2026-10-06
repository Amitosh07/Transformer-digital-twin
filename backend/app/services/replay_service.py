"""Background replay owns its session and always uses the common ingestion service."""

import logging
from time import sleep

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import ingestion_run_repo, telemetry_repo
from app.schemas.ingestion import ReplayIn, ReplayStatusOut
from app.services.ingestion_service import ingest_record
from app.services.quality_stats import QualityStats, parse_records

logger = logging.getLogger(__name__)


def start_replay(session: Session, request: ReplayIn) -> int:
    run = ingestion_run_repo.create_run(
        session,
        request.source_name,
        get_settings().schema_version,
        len(request.records or []),
    )
    run_id = run.id
    session.commit()
    return run_id


def get_replay_status(session: Session, run_id: int) -> ReplayStatusOut:
    row = ingestion_run_repo.get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Replay run was not found")
    return ReplayStatusOut.model_validate(row)


def run_replay(run_id: int, request: ReplayIn) -> None:
    with SessionLocal() as session:
        stats = QualityStats(row_count=len(request.records or []))
        try:
            if request.from_stored is not None:
                records = telemetry_repo.load_stored_window(
                    session,
                    request.from_stored.start,
                    request.from_stored.end,
                    request.transformer_id,
                )
                stats.row_count = len(records)
                for record in records:
                    stats.parsed(record)
            else:
                records, stats = parse_records(
                    request.records or [],
                    request.source_name,
                    transformer_id=request.transformer_id,
                    force_source=True,
                )
            records.sort(key=lambda row: (row.timestamp, row.transformer_id))
            ingestion_run_repo.update_run(session, run_id, stats.values(), "RUNNING")
            session.commit()
            previous = None
            for record in records:
                if previous is not None and request.speed_multiplier > 0:
                    delay = (record.timestamp - previous).total_seconds() / request.speed_multiplier
                    sleep(min(max(delay, 0), 5))
                result = ingest_record(
                    session,
                    record,
                    run_ml=request.run_ml,
                    reanalyze_missing=request.from_stored is not None,
                )
                if result.duplicate:
                    stats.duplicate_count += 1
                else:
                    stats.inserted_count += 1
                previous = record.timestamp
                ingestion_run_repo.update_run(session, run_id, stats.values(), "RUNNING")
                session.commit()
            ingestion_run_repo.update_run(session, run_id, stats.values(), "COMPLETED")
            session.commit()
        except Exception:
            session.rollback()
            logger.error("Replay failed run_id=%s", run_id)
            ingestion_run_repo.update_run(session, run_id, stats.values(), "FAILED")
            session.commit()
