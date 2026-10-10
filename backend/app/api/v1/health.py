from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.db.session import DatabaseSession
from app.schemas.health import HealthResponse
from app.schemas.readiness import ReadinessOut
from app.services.health import check_health
from app.services.readiness_service import check_ready

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    db: DatabaseSession, settings: Annotated[Settings, Depends(get_settings)]
) -> HealthResponse:
    return check_health(db, settings.schema_version)


@router.get(
    "/health/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut, "description": "Service is not ready"}},
)
def ready(
    request: Request, db: DatabaseSession, settings: Annotated[Settings, Depends(get_settings)]
) -> JSONResponse:
    result = check_ready(db, settings, getattr(request.app.state, "started", False))
    return JSONResponse(
        status_code=200 if result.status == "ready" else 503, content=result.model_dump(mode="json")
    )
