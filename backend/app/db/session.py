"""Sync psycopg sessions; connections always operate in UTC."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def SessionLocal() -> Session:
    """Create a session lazily so importing the app never opens a DB connection."""
    return get_session_factory()()


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_db)]
