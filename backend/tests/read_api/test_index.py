import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models.transformer import Transformer
from app.repositories.telemetry_repo import read_window_statement
from tests.read_api.conftest import BASE


def test_20k_window_uses_index_without_forcing_plan(db: Session) -> None:
    asset = f"TX-index-{uuid4().hex[:8]}"
    db.add(Transformer(id=asset, name=asset))
    db.flush()
    # SQL fixture bulk-loads only the planner dataset, independent of application ingestion.
    db.execute(
        text("""INSERT INTO telemetry (transformer_id, timestamp, schema_version)
        SELECT :asset, CAST(:start AS timestamptz) + make_interval(secs => n), '1.0.0'
        FROM generate_series(0, 19999) AS n"""),
        {"asset": asset, "start": BASE},
    )
    db.execute(text("ANALYZE telemetry"))
    statement = (
        read_window_statement(
            asset, BASE + timedelta(seconds=10000), BASE + timedelta(seconds=10059)
        )
        .order_by(text("timestamp ASC, id ASC"))
        .limit(60)
    )
    sql = statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    plan = db.execute(text("EXPLAIN (FORMAT JSON) " + str(sql))).scalar_one()[0]["Plan"]

    def nodes(node: dict) -> list[dict]:
        return [node] + [
            descendant for child in node.get("Plans", []) for descendant in nodes(child)
        ]

    print("INDEX_PLAN", json.dumps(plan))
    scans = [node for node in nodes(plan) if "Index" in node["Node Type"]]
    assert scans, plan
    indexes = {entry["name"]: entry for entry in inspect(db.connection()).get_indexes("telemetry")}
    assert any(
        indexes[node["Index Name"]]["column_names"] == ["transformer_id", "timestamp"]
        for node in scans
    )
    # No enable_seqscan override: PostgreSQL naturally selects a selective composite index.
    maintenance = inspect(db.connection()).get_indexes("maintenance_records")
    assert any(index["column_names"] == ["transformer_id", "timestamp"] for index in maintenance)
