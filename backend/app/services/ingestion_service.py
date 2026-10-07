"""The single telemetry write path shared by live, batch, replay and future MQTT."""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml_client.factory import get_ml_client
from app.ml_client.safe import safe_analyze
from app.repositories import analytics_repo, ingestion_run_repo, telemetry_repo, transformer_repo
from app.schemas.analytics import AnalyticsOut, MLResultIn
from app.schemas.ingestion import IngestionSummary, IngestResult
from app.schemas.quality import compute_data_quality_score, compute_is_missing_critical
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut
from app.services import hooks
from app.services.quality_stats import parse_records

logger = logging.getLogger(__name__)
CHUNK_SIZE = 1000


class _UnavailableClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        raise self.error


@dataclass
class _BatchContext:
    transformer: TransformerOut
    window: deque[TelemetryIn]
    stored: deque[TelemetryIn]

    def history_before(self, record: TelemetryIn) -> list[TelemetryIn]:
        while self.stored and self.stored[0].timestamp < record.timestamp:
            row = self.stored.popleft()
            # Existing rows enter once from the database snapshot; duplicate inputs never enter.
            if not self.window or self.window[-1].timestamp != row.timestamp:
                self.window.append(row)
        return [row for row in self.window if row.timestamp < record.timestamp]


def ingest_record(
    session: Session,
    record: TelemetryIn,
    *,
    run_ml: bool = True,
    _transformer: TransformerOut | None = None,
    _history: list[TelemetryIn] | None = None,
    _commit: bool = True,
    reanalyze_missing: bool = False,
) -> IngestResult:
    settings = get_settings()
    record = record.model_copy(update={"source_name": record.source_name or "api"})
    try:
        transformer = _transformer or TransformerOut.model_validate(
            transformer_repo.ensure_transformer(session, record.transformer_id),
        )
        transformer_repo.lock_for_ingestion(session, record.transformer_id)
        missing = compute_is_missing_critical(record)
        telemetry, duplicate = telemetry_repo.insert_telemetry(
            session,
            record,
            schema_version=settings.schema_version,
            is_missing_critical=missing,
            data_quality_score=compute_data_quality_score(record),
        )
        if duplicate and (
            not reanalyze_missing
            or not run_ml
            or analytics_repo.get_for_telemetry(session, telemetry.id) is not None
        ):
            result = IngestResult(telemetry_id=telemetry.id, duplicate=True)
        else:
            warnings = ["MISSING_CRITICAL"] if missing else []
            analytics_out = None
            if run_ml:
                history = (
                    _history
                    if _history is not None
                    else telemetry_repo.load_history(
                        session,
                        record.transformer_id,
                        record.timestamp,
                        settings.ml_history_window,
                    )
                )
                try:
                    client = get_ml_client()
                except Exception as exc:
                    client = _UnavailableClient(exc)
                ml_result = safe_analyze(client, transformer, record, history)
                analytics, created = analytics_repo.insert_analytics(
                    session, telemetry.id, ml_result
                )
                analytics_out = AnalyticsOut.model_validate(analytics)
                if ml_result.error_detail:
                    warnings.append("ML_UNAVAILABLE")
                if ml_result.inference_status == "INSUFFICIENT_DATA":
                    warnings.append("INSUFFICIENT_DATA")
                if created:
                    try:
                        with session.begin_nested():
                            hooks.evaluate_alerts(session, telemetry, analytics)
                    except Exception:
                        logger.warning(
                            "Alert hook failed transformer_id=%s timestamp=%s",
                            record.transformer_id,
                            record.timestamp.isoformat(),
                        )
                        warnings.append("ALERT_HOOK_FAILED")
            result = IngestResult(
                telemetry_id=telemetry.id,
                duplicate=duplicate,
                analytics=analytics_out,
                warnings=warnings,
            )
        if _commit:
            session.commit()
        return result
    except Exception:
        if _commit:
            session.rollback()
        raise


def ingest_batch(
    session: Session,
    rows: list[dict[str, Any]],
    *,
    run_ml: bool = True,
    source_name: str = "api",
) -> IngestionSummary:
    settings = get_settings()
    if len(rows) > settings.max_batch_size:
        raise ValueError("Batch exceeds MAX_BATCH_SIZE")
    records, stats = parse_records(rows, source_name)
    records.sort(key=lambda row: (row.transformer_id, row.timestamp))
    last_by_transformer = {row.transformer_id: row.timestamp for row in records}
    run = ingestion_run_repo.create_run(session, source_name, settings.schema_version, len(rows))
    run_id = run.id
    session.commit()
    contexts: dict[str, _BatchContext] = {}
    committed_inserted = 0
    try:
        for index, record in enumerate(records, 1):
            if record.transformer_id not in contexts:
                transformer = TransformerOut.model_validate(
                    transformer_repo.ensure_transformer(session, record.transformer_id),
                )
                stored = (
                    telemetry_repo.load_batch_history(
                        session,
                        record.transformer_id,
                        record.timestamp,
                        last_by_transformer[record.transformer_id],
                        settings.ml_history_window,
                    )
                    if run_ml
                    else []
                )
                contexts[record.transformer_id] = _BatchContext(
                    transformer=transformer,
                    window=deque(maxlen=settings.ml_history_window),
                    stored=deque(stored),
                )
            context = contexts[record.transformer_id]
            result = ingest_record(
                session,
                record,
                run_ml=run_ml,
                _transformer=context.transformer,
                _history=context.history_before(record) if run_ml else [],
                _commit=False,
            )
            if result.duplicate:
                stats.duplicate_count += 1
            else:
                stats.inserted_count += 1
                context.window.append(record)
            if index % CHUNK_SIZE == 0:
                ingestion_run_repo.update_run(session, run_id, stats.values(), "RUNNING")
                session.commit()
                committed_inserted = stats.inserted_count
        ingestion_run_repo.update_run(session, run_id, stats.values(), "COMPLETED")
        session.commit()
        return stats.summary(run_id)
    except Exception:
        session.rollback()
        stats.inserted_count = committed_inserted
        ingestion_run_repo.update_run(session, run_id, stats.values(), "FAILED")
        session.commit()
        raise
