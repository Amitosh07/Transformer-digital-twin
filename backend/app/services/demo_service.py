"""Explicitly authorized demo reset, isolated from ingestion and ML behavior."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import demo_repo
from app.schemas.demo import DemoResetOut


def require_demo_environment(settings: Settings) -> None:
    if settings.env.strip().casefold() == "production":
        raise ValueError("Demo reset is forbidden when ENV=production")


def reset_demo(
    session: Session, settings: Settings, *, yes: bool, include_transformers: bool = False
) -> DemoResetOut:
    require_demo_environment(settings)
    if not yes:
        raise ValueError("Demo reset requires --yes")
    try:
        deleted = demo_repo.delete_demo_data(session, include_transformers)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return DemoResetOut(deleted=deleted)
