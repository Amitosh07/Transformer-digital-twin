from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.transformer import Transformer
from app.schemas.transformer import TransformerIn


def ensure_transformer(session: Session, transformer_id: str) -> Transformer:
    statement = (
        insert(Transformer)
        .values(id=transformer_id, name=transformer_id)
        .on_conflict_do_nothing(
            index_elements=[Transformer.id],
        )
        .returning(Transformer)
    )
    row = session.scalar(statement)
    if row is None:
        row = session.scalar(select(Transformer).where(Transformer.id == transformer_id))
    if row is None:
        raise RuntimeError("Transformer creation did not return a row")
    return row


def get(session: Session, transformer_id: str) -> Transformer | None:
    return session.get(Transformer, transformer_id)


def read_page(session: Session, limit: int, offset: int) -> tuple[list[Transformer], int]:
    total = session.scalar(select(func.count()).select_from(Transformer)) or 0
    rows = session.scalars(select(Transformer).order_by(Transformer.id).limit(limit).offset(offset))
    return list(rows), total


def create(session: Session, payload: TransformerIn) -> Transformer | None:
    return session.scalar(
        insert(Transformer)
        .values(**payload.model_dump())
        .on_conflict_do_nothing(index_elements=[Transformer.id])
        .returning(Transformer)
    )


def patch(session: Session, row: Transformer, changes: dict[str, Any]) -> Transformer:
    for key, value in changes.items():
        setattr(row, key, value)
    session.flush()
    session.refresh(row)
    return row
