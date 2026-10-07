"""Private chunk buffers; ingest_record remains the entry point for every telemetry write."""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Alert, MaintenanceRecord, Telemetry
from app.repositories import alert_repo, analytics_repo, maintenance_repo, telemetry_repo
from app.schemas.analytics import MLResultIn
from app.schemas.quality import compute_data_quality_score, compute_is_missing_critical
from app.schemas.telemetry import TelemetryIn
from app.services import hooks

CACHE_KEY = "ingestion_lifecycle_cache"
logger = logging.getLogger(__name__)


class LifecycleCache:
    def __init__(self, session: Session, assets: list[str]) -> None:
        self.alerts = {asset: alert_repo.active(session, asset) for asset in assets}
        self.maintenance = {
            asset: maintenance_repo.open_records(session, asset) for asset in assets
        }
        self.new_alerts: list[Alert] = []
        self.new_maintenance: list[MaintenanceRecord] = []

    def flush(self, session: Session) -> None:
        # Existing alerts can resolve before a new active episode uses the same unique key.
        session.flush()
        if self.new_alerts:
            values = [
                {
                    column.name: getattr(row, column.name)
                    for column in Alert.__table__.columns
                    if column.name not in {"id", "created_at"}
                }
                for row in self.new_alerts
            ]
            ids = list(
                session.scalars(
                    insert(Alert)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=[Alert.transformer_id, Alert.alert_type],
                        index_where=text("status IN ('OPEN','ACKNOWLEDGED')"),
                    )
                    .returning(Alert.id)
                )
            )
            if len(ids) != len(values):
                # Replay using the ordinary conflict/update path after rolling back the savepoint.
                raise RuntimeError("Lifecycle conflict requires row-by-row reconciliation")
        if self.new_maintenance:
            values = [
                {
                    column.name: getattr(row, column.name)
                    for column in MaintenanceRecord.__table__.columns
                    if column.name not in {"id", "created_at"}
                }
                for row in self.new_maintenance
            ]
            session.execute(insert(MaintenanceRecord).values(values))


class BatchChunk:
    def __init__(self, records: list[TelemetryIn], settings: Settings) -> None:
        self.records = records
        self.settings = settings
        self.rows: dict[tuple[str, datetime], Telemetry] | None = None
        self.pending: list[tuple[Telemetry, MLResultIn]] = []
        self.last_key = (records[-1].transformer_id, records[-1].timestamp)

    def telemetry(self, session: Session, record: TelemetryIn) -> tuple[Telemetry, bool]:
        if self.rows is None:
            values = [
                row.model_dump(mode="python")
                | {
                    "schema_version": self.settings.schema_version,
                    "is_missing_critical": compute_is_missing_critical(row),
                    "data_quality_score": compute_data_quality_score(row),
                }
                for row in self.records
            ]
            self.rows = telemetry_repo.insert_many(session, values)
        row = self.rows.get((record.transformer_id, record.timestamp))
        if row is not None:
            return row, False
        # Only external writers bypassing the parent lock can reach this conflict path.
        return telemetry_repo.insert_telemetry(
            session,
            record,
            schema_version=self.settings.schema_version,
            is_missing_critical=compute_is_missing_critical(record),
            data_quality_score=compute_data_quality_score(record),
        )

    def finish(self, session: Session) -> None:
        if not self.pending:
            return
        analytics = analytics_repo.insert_many(
            session,
            [
                result.model_dump(mode="python") | {"telemetry_id": row.id}
                for row, result in self.pending
            ],
        )
        pairs = [(row, analytics[row.id]) for row, _ in self.pending if row.id in analytics]
        try:
            with session.begin_nested():
                cache = LifecycleCache(session, sorted({row.transformer_id for row, _ in pairs}))
                session.info[CACHE_KEY] = cache
                try:
                    with session.no_autoflush:
                        for telemetry, analysis in pairs:
                            hooks.evaluate_alerts(session, telemetry, analysis)
                        cache.flush(session)
                finally:
                    session.info.pop(CACHE_KEY, None)
        except Exception:
            # A failed chunk hook must not discard successful per-record hook mutations.
            # The normal savepoint/conflict path remains the recovery safety net.
            for telemetry, analysis in pairs:
                try:
                    with session.begin_nested():
                        hooks.evaluate_alerts(session, telemetry, analysis)
                except Exception:
                    logger.warning(
                        "Alert hook failed transformer_id=%s timestamp=%s",
                        telemetry.transformer_id,
                        telemetry.timestamp.isoformat(),
                    )
