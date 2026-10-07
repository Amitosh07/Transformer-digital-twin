"""Database readiness without exposing database exception details."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from app.repositories.health import ping_database


@lru_cache
def expected_heads() -> set[str]:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def check(session: Session) -> bool:
    ping_database(session)
    current = set(MigrationContext.configure(session.connection()).get_current_heads())
    return current == expected_heads()
