"""Opt-in demo administration with a separate token and production refusal."""

from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import Settings, get_settings
from app.db.session import DatabaseSession
from app.schemas.common import ErrorResponse
from app.schemas.demo import DemoResetOut
from app.services.demo_service import reset_demo

router = APIRouter(tags=["demo admin"])


def authorize_reset(
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> Settings:
    if not settings.demo_reset_enabled:
        raise HTTPException(404, "Not found")
    if settings.env.strip().casefold() == "production":
        raise HTTPException(403, "Demo reset is forbidden in production")
    expected = settings.demo_admin_token
    if expected is None or not expected.get_secret_value():
        raise HTTPException(403, "Demo admin token is not configured")
    if token is None or not compare_digest(token.encode(), expected.get_secret_value().encode()):
        raise HTTPException(403, "Invalid demo admin token")
    return settings


@router.post(
    "/admin/demo/reset",
    response_model=DemoResetOut,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def post_reset(
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(authorize_reset)],
    include_transformers: Annotated[bool, Query()] = False,
) -> DemoResetOut:
    return reset_demo(db, settings, yes=True, include_transformers=include_transformers)
