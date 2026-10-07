import json
from pathlib import Path

from conftest import migration_config
from sqlalchemy import Engine, inspect

from alembic import command
from app.main import create_app
from app.schemas.alert import AlertOut


def test_migration_0003_upgrade_downgrade_check(database_url: str, db_engine: Engine) -> None:
    config = migration_config(database_url)
    command.downgrade(config, "0002")
    old = inspect(db_engine)
    assert not {"clear_count", "resolved_at"} & {item["name"] for item in old.get_columns("alerts")}
    assert "uq_alerts_active_transformer_type" not in {
        item["name"] for item in old.get_indexes("alerts")
    }
    command.upgrade(config, "head")
    inspector = inspect(db_engine)
    columns = {item["name"]: item for item in inspector.get_columns("alerts")}
    assert columns["clear_count"]["nullable"] is False
    assert columns["clear_count"]["default"] == "0"
    assert columns["resolved_at"]["nullable"] is True
    assert columns["resolved_at"]["type"].timezone is True
    index = next(
        item
        for item in inspector.get_indexes("alerts")
        if item["name"] == "uq_alerts_active_transformer_type"
    )
    assert index["unique"]
    assert index["column_names"] == ["transformer_id", "alert_type"]
    assert "OPEN" in str(index["dialect_options"]["postgresql_where"])
    assert "ACKNOWLEDGED" in str(index["dialect_options"]["postgresql_where"])
    command.check(config)


def test_public_lifecycle_contract_and_canonical_names() -> None:
    app = create_app()
    schema = app.openapi()
    assert "clear_count" not in AlertOut.model_fields
    assert {"last_seen_at", "resolved_at"} <= AlertOut.model_fields.keys()
    for path in [
        "/api/v1/alerts/{id}",
        "/api/v1/alerts/{id}/acknowledge",
        "/api/v1/alerts/{id}/resolve",
        "/api/v1/maintenance/{id}",
    ]:
        assert path in schema["paths"]
    backend = Path(__file__).resolve().parents[2]
    sources = [
        backend / name
        for name in [
            "app/services/alert_service.py",
            "app/services/maintenance_service.py",
            "app/api/v1/alerts_write.py",
            "alembic/versions/0003_alert_lifecycle.py",
        ]
    ]
    sources.extend(Path(__file__).parent.glob("*.py"))
    documents = [json.dumps(schema)] + [source.read_text() for source in sources]
    excluded = ["v" + "l12", "v" + "l23", "v" + "l31"]
    unwanted_wording = ["confirmed" + " fault", "fault" + " detected"]
    raw_names = ["OT" + "I", "WT" + "I", "AT" + "I", "VL" + "1", "IL" + "1"]
    import re

    for document in documents:
        assert not any(name in document.casefold() for name in excluded + unwanted_wording)
        assert not any(re.search(r"\b" + name + r"\b", document) for name in raw_names)
