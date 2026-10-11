from typing import Annotated, Literal
from fastapi import APIRouter, Query
from app.api.v1.query_dependencies import WindowQuery
from app.db.session import DatabaseSession
from app.services import analytics_resources

router = APIRouter(tags=['RUL and energy'])

@router.get('/transformers/{id}/rul')
def rul(id: str, db: DatabaseSession):
    return analytics_resources.rul(db,id)

@router.get('/transformers/{id}/rul/projection')
def projection(id: str, db: DatabaseSession):
    """Separate additive resource; the frozen H00 RUL object remains unchanged."""
    return analytics_resources.projection(db,id)

@router.get('/transformers/{id}/energy')
def energy(id: str, db: DatabaseSession, time: WindowQuery,
           window: Annotated[Literal['1h','6h','24h','7d'],Query()]='1h'):
    return analytics_resources.energy(db,id,time,window)
