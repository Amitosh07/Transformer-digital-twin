"""Receipt/checkpoint writes participate in the caller's SQL transaction."""
from sqlalchemy import func, text, literal_column
from sqlalchemy.dialects.postgresql import insert
from app.models.processing import IngestionReceipt, MLCheckpoint


def checkpoint(session, asset):
    row = session.get(MLCheckpoint, asset, populate_existing=True)
    return row.checkpoint if row else None


def checkpoint_revision(session, asset):
    """PostgreSQL MVCC token changes on every row write, including content edits.

    This is only an internal warm-owner cache token, never a contract version.
    Missing/changed/frozen tokens always require full checkpoint validation.
    """
    return session.scalar(text('SELECT xmin::text FROM ml_checkpoints WHERE transformer_id=:asset'),
                          {'asset': asset})


def save_checkpoint(session, asset, value):
    return session.execute(insert(MLCheckpoint).values(transformer_id=asset, checkpoint=value)
        .on_conflict_do_update(index_elements=[MLCheckpoint.transformer_id],
            set_={'checkpoint': value, 'updated_at': func.now()})
        .returning(literal_column('xmin::text'))).scalar_one()


def receipt(session, snapshot):
    return session.get(IngestionReceipt, snapshot)


def save_receipt(session, record, payload_hash, telemetry, *, status='COMMITTED',
                 outcome='ACCEPTED', accepted_hash=None, ml_status=None, reason=None):
    session.execute(insert(IngestionReceipt).values(snapshot_id=payload_hash, payload_hash=payload_hash,
        accepted_payload_hash=accepted_hash or payload_hash, transformer_id=record.transformer_id,
        event_time=record.timestamp, telemetry_id=telemetry.id if telemetry else None,
        status=status, ingestion_outcome=outcome, ml_status=ml_status, reason=reason)
        .on_conflict_do_nothing(index_elements=[IngestionReceipt.snapshot_id]))
