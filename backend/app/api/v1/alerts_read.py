from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.v1.query_dependencies import PageQuery, WindowQuery
from app.api.v1.read_examples import ALERT, page_example, response_example
from app.db.session import DatabaseSession
from app.schemas.alert import AlertOut
from app.schemas.common import Page
from app.services import query_service

router = APIRouter(tags=["alerts"])


@router.get(
    "/transformers/{id}/alerts",
    response_model=Page[AlertOut],
    responses=response_example(page_example(ALERT)),
)
def get_alerts(
    id: str,
    db: DatabaseSession,
    time: WindowQuery,
    page: PageQuery,
    severity: Annotated[Literal["INFO", "WARNING", "CRITICAL"] | None, Query()] = None,
    status: Annotated[Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"] | None, Query()] = None,
) -> Page[AlertOut]:
    return query_service.alerts(db, id, time, page, severity, status)
