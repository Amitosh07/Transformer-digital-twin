from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.transformer import Transformer


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
