from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db, get_engine, get_session_factory


def test_dependency_closes_session(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db.session as module

    session = Mock(spec=Session)
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(module, "SessionLocal", lambda: session)
    dependency = get_db()
    assert next(dependency) is session
    dependency.close()
    session.__exit__.assert_called_once()


@pytest.mark.postgres
def test_session_factory(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    try:
        assert get_engine() is get_engine()
        assert get_session_factory() is get_session_factory()
        with SessionLocal() as session:
            assert session.scalar(text("SHOW timezone")) == "UTC"
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        get_settings.cache_clear()
