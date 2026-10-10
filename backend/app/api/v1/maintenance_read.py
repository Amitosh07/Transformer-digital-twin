from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.v1.query_dependencies import PageQuery, WindowQuery
from app.api.v1.read_examples import MAINTENANCE, page_example, response_example
from app.db.session import DatabaseSession
from app.schemas.common import Page
from app.schemas.maintenance import MaintenanceOut
from app.services import query_service

router = APIRouter(tags=["maintenance"])


@router.get(
    "/transformers/{id}/maintenance",
    response_model=Page[MaintenanceOut],
    responses=response_example(page_example(MAINTENANCE)),
)
def get_maintenance(
    id: str,
    db: DatabaseSession,
    time: WindowQuery,
    page: PageQuery,
    status: Annotated[Literal["OPEN", "DONE", "DISMISSED"] | None, Query()] = None,
) -> Page[MaintenanceOut]:
    return query_service.maintenance(db, id, time, page, status)
