from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import create_app
from app.models import Alert, Analytics, Telemetry
from app.schemas.ingestion import ReplayIn
from app.services import replay_service
from app.services.ingestion_service import ingest_record
from tests.performance.test_differential import mixed


def test_http_mqtt_style_and_real_replay_concurrently(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = "TX-three-transports-" + uuid4().hex
    factory = sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", factory)
    app = create_app()

    def database() -> Iterator[Session]:
        with factory() as session:
            session.execute(text("SET lock_timeout = '15s'"))
            yield session

    app.dependency_overrides[get_db] = database
    request = ReplayIn(
        transformer_id=asset,
        source_name="replay-test",
        records=[mixed(asset, index).model_dump(mode="json") for index in range(60, 120)],
    )
    with factory() as session:
        run_id = replay_service.start_replay(session, request)
    barrier = Barrier(3)
    with TestClient(app) as client:

        def http_batch() -> None:
            barrier.wait(timeout=10)
            response = client.post(
                "/api/v1/telemetry/batch",
                json={
                    "records": [
                        mixed(asset, index).model_dump(mode="json") for index in reversed(range(60))
                    ]
                },
            )
            assert response.status_code == 200

        def mqtt_style() -> None:
            barrier.wait(timeout=10)
            with factory() as session:
                session.execute(text("SET lock_timeout = '15s'"))
                for index in range(30, 90):
                    ingest_record(session, mixed(asset, index), _commit=False)
                session.commit()

        def replay() -> None:
            barrier.wait(timeout=10)
            replay_service.run_replay(run_id, request)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(function) for function in (http_batch, mqtt_style, replay)]
            for future in futures:
                future.result(timeout=45)
    with factory() as session:
        for model in (Telemetry, Analytics):
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.transformer_id == asset)
                )
                == 120
            )
        assert replay_service.get_replay_status(session, run_id).status == "COMPLETED"
        active = list(
            session.scalars(
                select(Alert).where(
                    Alert.transformer_id == asset, Alert.status.in_(["OPEN", "ACKNOWLEDGED"])
                )
            )
        )
        assert len({row.alert_type for row in active}) == len(active)
