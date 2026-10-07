from fastapi import APIRouter

from app.api.v1.read_examples import LATEST, response_example
from app.db.session import DatabaseSession
from app.schemas.state import LatestStateOut
from app.services import query_service

router = APIRouter(tags=["latest state"])


@router.get(
    "/transformers/{id}/latest",
    response_model=LatestStateOut,
    description="Latest telemetry and its analytics. Fault outputs describe proxy risk.",
    responses=response_example(LATEST),
)
def get_latest(id: str, db: DatabaseSession) -> LatestStateOut:
    return query_service.latest(db, id)
