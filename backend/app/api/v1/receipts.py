"""Read-only durable SQL receipts; a transport PUBACK is never a receipt."""
from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from app.db.session import DatabaseSession
from app.repositories import processing_repo

router = APIRouter(tags=['ingestion'])


@router.get('/ingestion/status')
def get_status():
    from app.services.ingestion_diagnostics import snapshot
    return snapshot()


@router.get('/ingestion/receipts/{snapshot_id}')
def get_receipt(db: DatabaseSession, snapshot_id: str = Path(pattern='^[0-9a-f]{64}$')):
    row = processing_repo.receipt(db, snapshot_id)
    if row is None or snapshot_id in db.info.get('h02_pending_receipts', set()):
        return JSONResponse(status_code=404, content={'error': {'code': 'RECEIPT_NOT_COMMITTED',
            'message': 'No committed receipt exists for this snapshot', 'details': {'snapshot_id': snapshot_id}}})
    return {'schema_version': '1.1.0', 'receipt_status': row.status,
        'snapshot_id': row.snapshot_id, 'payload_hash': row.payload_hash,
        'transformer_id': row.transformer_id, 'timestamp': row.event_time,
        'received_at': row.received_at, 'committed_at': row.committed_at if row.status == 'COMMITTED' else None,
        'accepted_snapshot_id': row.accepted_payload_hash, 'accepted_payload_hash': row.accepted_payload_hash,
        'ingestion_outcome': row.ingestion_outcome, 'analytics_status': row.ml_status or 'UNAVAILABLE',
        'state_coverage_loss': row.ml_status not in ('AVAILABLE', 'INSUFFICIENT_DATA')}
