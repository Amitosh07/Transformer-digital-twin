from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.session import DatabaseSession
from app.schemas.health import HealthResponse
from app.services.health import check_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    db: DatabaseSession, settings: Annotated[Settings, Depends(get_settings)]
) -> HealthResponse:
    return check_health(db, settings.schema_version)
