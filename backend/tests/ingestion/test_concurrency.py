from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.models import Analytics, Telemetry
from app.services.ingestion_service import ingest_batch

from .conftest import make_record


def test_two_overlapping_batches_do_not_deadlock(db_engine: Engine, asset_id: str) -> None:
    barrier = Barrier(2)

    def run(start: int) -> tuple[int, int]:
        with Session(db_engine) as session:
            session.execute(text("SET lock_timeout = '10s'"))
            barrier.wait(timeout=10)
            # Opposing input orders exercise the service's consistent lock order.
            rows = [make_record(asset_id, value) for value in reversed(range(start, start + 30))]
            result = ingest_batch(session, rows)
            return result.inserted_count, result.duplicate_count

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, value) for value in [0, 15]]
        summaries = [future.result(timeout=30) for future in futures]
    assert sum(result[0] for result in summaries) == 45
    assert sum(result[1] for result in summaries) == 15
    with Session(db_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Telemetry)
                .where(
                    Telemetry.transformer_id == asset_id,
                )
            )
            == 45
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Analytics)
                .where(
                    Analytics.transformer_id == asset_id,
                )
            )
            == 45
        )
