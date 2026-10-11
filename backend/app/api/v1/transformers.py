from fastapi import APIRouter, Query
from typing import Literal

from app.api.v1.query_dependencies import PageQuery
from app.api.v1.read_examples import TRANSFORMER, page_example, response_example
from app.db.session import DatabaseSession
from app.schemas.common import Page
from app.schemas.transformer import TransformerIn, TransformerOut, TransformerPatch
from app.services import query_service

router = APIRouter(tags=["transformers"])


@router.get(
    "/transformers",
    response_model=Page[TransformerOut],
    responses=response_example(page_example(TRANSFORMER)),
)
def list_transformers(db: DatabaseSession, page: PageQuery,
                      scope: Literal['active', 'all'] = Query(default='active')) -> Page[TransformerOut]:
    return query_service.transformers(db, page, scope)


@router.post(
    "/transformers",
    response_model=TransformerOut,
    status_code=201,
    responses=response_example(TRANSFORMER, 201),
)
def create_transformer(payload: TransformerIn, db: DatabaseSession) -> TransformerOut:
    return query_service.create_transformer(db, payload)


@router.get(
    "/transformers/{id}", response_model=TransformerOut, responses=response_example(TRANSFORMER)
)
def get_transformer(id: str, db: DatabaseSession) -> TransformerOut:
    return query_service.transformer(db, id)


@router.patch(
    "/transformers/{id}",
    response_model=TransformerOut,
    description="Only supplied fields change. Null clears nullable nameplate configuration.",
    responses=response_example(TRANSFORMER),
)
def patch_transformer(id: str, payload: TransformerPatch, db: DatabaseSession) -> TransformerOut:
    return query_service.patch_transformer(db, id, payload)
