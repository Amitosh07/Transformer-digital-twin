from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.models import Alert, MaintenanceRecord, Telemetry
from app.services.ingestion_service import ingest_batch
from tests.alerts.conftest import BASE, record


@pytest.mark.parametrize("starts", [(0, 0), (0, 10)])
def test_concurrent_trip_batches_no_duplicate_active_alert_or_deadlock(
    db_engine: Engine,
    asset_id: str,
    starts: tuple[int, int],
) -> None:
    barrier = Barrier(2)

    def run(start: int) -> tuple[int, int]:
        with Session(db_engine) as session:
            session.execute(text("SET lock_timeout = '10s'"))
            barrier.wait(timeout=10)
            rows = [
                record(asset_id, second, oil_temp_trip=1).model_dump(mode="json")
                for second in reversed(range(start, start + 20))
            ]
            summary = ingest_batch(session, rows)
            assert summary.parse_error_count == 0
            return summary.inserted_count, summary.duplicate_count

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, start) for start in starts]
        counts = [future.result(timeout=45) for future in futures]
    unique_count = 20 + max(starts)
    assert sum(count[0] for count in counts) == unique_count
    assert sum(count[1] for count in counts) == 40 - unique_count
    with Session(db_engine) as session:
        rows = list(session.scalars(select(Alert).where(Alert.transformer_id == asset_id)))
        trip = [row for row in rows if row.alert_type == "OIL_TEMP_TRIP"]
        assert len(trip) == 1 and trip[0].status == "OPEN"
        assert trip[0].last_seen_at == BASE + timedelta(seconds=unique_count - 1)
        assert len({row.alert_type for row in rows}) == len(rows)
        assert (
            session.scalar(
                select(func.count())
                .select_from(Telemetry)
                .where(Telemetry.transformer_id == asset_id)
            )
            == unique_count
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(MaintenanceRecord)
                .where(MaintenanceRecord.transformer_id == asset_id)
            )
            == 1
        )
