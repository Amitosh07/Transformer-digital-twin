import pytest
from conftest import migration_config
from sqlalchemy import Engine, inspect

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
