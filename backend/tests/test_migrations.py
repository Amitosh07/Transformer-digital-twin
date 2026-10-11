import pytest
from conftest import migration_config
from sqlalchemy import Engine, inspect
from sqlalchemy import text
from uuid import uuid4

from alembic import command
from app.db.base import Base


@pytest.mark.postgres
def test_migration_round_trip(database_url: str, db_engine: Engine) -> None:
    config = migration_config(database_url)
    command.downgrade(config, "base")
    assert set(inspect(db_engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert set(inspect(db_engine).get_table_names()) == set(Base.metadata.tables) | {
        "alembic_version"
    }
    command.check(config)
    inspector = inspect(db_engine)
    for table in ["telemetry", "analytics", "alerts"]:
        index = next(
            item for item in inspector.get_indexes(table) if item["name"].endswith("timestamp_desc")
        )
        assert index["column_names"] == ["transformer_id", "timestamp"]
        assert index["column_sorting"]["timestamp"] == ("desc",)
    assert len(inspector.get_check_constraints("telemetry")) == 3
    assert len(inspector.get_check_constraints("analytics")) == 6


@pytest.mark.postgres
def test_h02_upgrade_preserves_legacy_rows(database_url: str, db_engine: Engine):
    config = migration_config(database_url)
    command.downgrade(config, '0003')
    asset = 'migration-' + uuid4().hex
    with db_engine.begin() as connection:
        connection.execute(text('INSERT INTO transformers (id, name) VALUES (:id, :id)'), {'id': asset})
        connection.execute(text("INSERT INTO telemetry (transformer_id, timestamp, schema_version, oil_temp_trip) VALUES (:id, '2026-10-09T00:00:00Z', '1.0.0', 1)"), {'id': asset})
    command.upgrade(config, 'head')
    with db_engine.connect() as connection:
        row = connection.execute(text('SELECT acquisition, payload_hash, oil_temp_trip FROM telemetry WHERE transformer_id=:id'), {'id': asset}).one()
        assert row.acquisition is None and row.payload_hash is None and row.oil_temp_trip == 1
        assert connection.scalar(text('SELECT schema_version FROM transformers WHERE id=:id'), {'id': asset}) == '1.0.0'
    command.check(config)
