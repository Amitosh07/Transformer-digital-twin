"""Profile production ingestion in an automatically removed PostgreSQL database."""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.ml_client.factory import close_ml_client
from app.repositories import analytics_repo, telemetry_repo, transformer_repo
from app.schemas.telemetry import TelemetryIn
from app.services import hooks, ingestion_service

BACKEND = Path(__file__).resolve().parents[1]


class Profiler:
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.stage_seconds: dict[str, float] = defaultdict(float)
        self.stage_calls: Counter = Counter()
        self.sql_seconds: dict[str, float] = defaultdict(float)
        self.sql_count: Counter = Counter()
        self.statement_kinds: Counter = Counter()

    def wrap(self, name: str, function: Any) -> Any:
        @wraps(function)
        def timed(*args: Any, **kwargs: Any) -> Any:
            self.stack.append(name)
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.stage_seconds[name] += perf_counter() - start
                self.stage_calls[name] += 1
                self.stack.pop()

        return timed

    def before(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        context.profile_start = perf_counter()
        context.profile_stage = self.stack[-1] if self.stack else "other"
        self.statement_kinds[statement.split()[0].upper()] += 1

    def after(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        stage = context.profile_stage
        self.sql_count[stage] += 1
        self.sql_seconds[stage] += perf_counter() - context.profile_start

    @contextmanager
    def instrument(self, engine: Any) -> Any:
        targets = [
            (ingestion_service, "ingest_record", "record"),
            (ingestion_service, "parse_records", "validation_quality"),
            (ingestion_service, "safe_analyze", "ml"),
            (transformer_repo, "ensure_transformer", "transformer"),
            (transformer_repo, "lock_for_ingestion", "transformer_lock"),
            (telemetry_repo, "insert_telemetry", "telemetry_insert"),
            (telemetry_repo, "load_history", "history"),
            (telemetry_repo, "load_batch_history", "batch_history"),
            (analytics_repo, "insert_analytics", "analytics_insert"),
            (hooks, "evaluate_alerts", "alert_maintenance_hook"),
        ]
        from contextlib import ExitStack

        for module, attribute, name in [
            (telemetry_repo, "existing_keys", "duplicate_prefilter"),
            (telemetry_repo, "insert_many", "bulk_telemetry"),
            (analytics_repo, "insert_many", "bulk_analytics"),
        ]:
            if hasattr(module, attribute):
                targets.append((module, attribute, name))
        event.listen(engine, "before_cursor_execute", self.before)
        event.listen(engine, "after_cursor_execute", self.after)
        try:
            with ExitStack() as stack:
                for module, attribute, name in targets:
                    stack.enter_context(
                        patch.object(module, attribute, self.wrap(name, getattr(module, attribute)))
                    )
                yield
        finally:
            event.remove(engine, "before_cursor_execute", self.before)
            event.remove(engine, "after_cursor_execute", self.after)

    def report(self, elapsed: float, count: int) -> dict[str, Any]:
        return {
            "elapsed_seconds": round(elapsed, 6),
            "rows": count,
            "sql_statements": sum(self.sql_count.values()),
            "sql_statements_per_row": round(sum(self.sql_count.values()) / count, 6),
            "sql_seconds": round(sum(self.sql_seconds.values()), 6),
            "statement_kinds": dict(self.statement_kinds),
            "stages": {
                name: {
                    "calls": self.stage_calls[name],
                    "inclusive_seconds": round(self.stage_seconds[name], 6),
                    "sql_count": self.sql_count[name],
                    "sql_seconds": round(self.sql_seconds[name], 6),
                }
                for name in sorted(self.stage_seconds.keys() | self.sql_count.keys())
            },
        }


def payload(asset: str, second: int) -> dict[str, Any]:
    return {
        "transformer_id": asset,
        "timestamp": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=second)).isoformat(),
        "oil_temperature": 42,
        "oil_level": 8,
        "oil_temp_alarm": 0,
        "current_l1": 0,
        "current_l2": 0,
        "current_l3": 0,
        "phase_voltage_l1": 0,
        "phase_voltage_l2": 0,
        "phase_voltage_l3": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--single-rows", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 1 or args.single_rows < 1:
        parser.error("row counts must be positive")
    url = make_url(os.environ.get("TEST_DATABASE_URL", get_settings().database_url))
    database = "transformer_profile_" + uuid4().hex
    admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    test_url = url.set(database=database).render_as_string(hide_password=False)
    engine = None
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        config.attributes["database_url"] = test_url
        command.upgrade(config, "head")
        os.environ.update(
            DATABASE_URL=test_url,
            MAX_BATCH_SIZE=str(args.rows),
            ML_BACKEND="stub",
            MQTT_ENABLED="false",
            LOG_LEVEL="WARNING",
        )
        get_settings.cache_clear()
        close_ml_client()
        engine = create_engine(test_url, connect_args={"options": "-c timezone=UTC"})
        app = create_app()

        def sessions() -> Any:
            with Session(engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = sessions
        reports = {}
        with TestClient(app) as client:
            rows = [payload("TX-profile-batch", second) for second in range(args.rows)]
            for name, data, run_ml in [
                ("initial", rows, True),
                ("identical_reload", rows, True),
                (
                    "without_ml",
                    [payload("TX-profile-no-ml", second) for second in range(args.rows)],
                    False,
                ),
            ]:
                profiler = Profiler()
                with profiler.instrument(engine):
                    start = perf_counter()
                    response = client.post(
                        "/api/v1/telemetry/batch",
                        params={"run_ml": str(run_ml).lower()},
                        json={"records": data},
                    )
                    elapsed = perf_counter() - start
                response.raise_for_status()
                reports[name] = profiler.report(elapsed, args.rows) | {"summary": response.json()}
                print(name + " " + json.dumps(reports[name]), flush=True)
            for name in ["single_http", "mqtt_style"]:
                profiler = Profiler()
                with profiler.instrument(engine):
                    start = perf_counter()
                    for second in range(args.single_rows):
                        row = payload("TX-profile-" + name, second)
                        if name == "single_http":
                            client.post("/api/v1/telemetry", json=row).raise_for_status()
                        else:
                            with Session(engine, expire_on_commit=False) as session:
                                ingestion_service.ingest_record(
                                    session, TelemetryIn.model_validate(row), _commit=False
                                )
                                session.commit()
                    elapsed = perf_counter() - start
                reports[name] = profiler.report(elapsed, args.single_rows)
                print(name + " " + json.dumps(reports[name]), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    finally:
        close_ml_client()
        if engine is not None:
            engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
