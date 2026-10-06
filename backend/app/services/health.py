import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.health import ping_database
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def check_health(session: Session, schema_version: str) -> HealthResponse:
    try:
        ping_database(session)
    except SQLAlchemyError:
        logger.warning("Database health check failed")
        return HealthResponse(status="degraded", db="error", schema_version=schema_version)
    return HealthResponse(status="ok", db="ok", schema_version=schema_version)
