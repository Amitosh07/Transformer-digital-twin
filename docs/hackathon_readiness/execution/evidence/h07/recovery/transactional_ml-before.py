"""Transaction-private H01 sessions; public memory changes only after SQL commit.

Intermediate batch checkpoints hydrate PRIVATE speculative branches, never the
committed owner. The final candidate is installed after the actual commit.
"""
import logging
from threading import RLock, Lock
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.repositories import processing_repo
from app.ml_client.base import parse_ml_result, validate_result_identity

logger = logging.getLogger(__name__)
KEY = 'h02_transactional_ml'
_locks = {}
_guard = Lock()


def lock_assets(session, assets):
    context = session.info.setdefault(KEY, {'locks': {}, 'branches': {}, 'results': [], 'committed': False})
    for asset in sorted(set(assets)):
        if asset in context['locks']:
            continue
        if context['locks'] and asset < max(context['locks']):
            raise RuntimeError('Acquire all batch assets in sorted order before ingestion')
        with _guard:
            lock = _locks.setdefault(asset, RLock())
        lock.acquire()
        context['locks'][asset] = lock


def prepare(session, client, transformer, record, history):
    from ml.pipeline import PipelineSession, UnifiedMLPipeline
    context = session.info[KEY]
    asset = record.transformer_id
    from app.services.analytics_resources import runtime_transformer
    configured_transformer = runtime_transformer(transformer)
    owner = client.transactional_runtime()
    branch = context['branches'].get(asset)
    if branch is None:
        staging = PipelineSession(UnifiedMLPipeline(owner.pipeline.bundle))
        saved = processing_repo.checkpoint(session, asset)
        if saved is not None:
            # Database is authoritative after a commit/install crash, including
            # failed restore quarantine. Do not invent a clean protection state.
            staging.import_checkpoint(saved, configured_transformer)
        branch = {'runtime': staging, 'owner': owner, 'candidate': None,
                  'transformer': configured_transformer}
        context['branches'][asset] = branch
    staging = branch['runtime']
    previous = branch['candidate']
    if previous is not None:
        # The previous SQL writes are still uncommitted. This private branch is
        # speculative state for the next sample; never a public committed owner.
        staging.discard(previous)
        staging.import_checkpoint(previous.checkpoint, branch['transformer'])
        branch['candidate'] = None
    committed_checkpoint = staging.export_checkpoint(asset)
    if committed_checkpoint is not None:
        from datetime import datetime
        last = datetime.fromisoformat(committed_checkpoint['committed_event_time'].replace('Z', '+00:00'))
        # Accepted-but-unanalysed rows are not forward state. Do not replay them
        # implicitly after an outage; the current observation exposes the gap.
        history = [row for row in history if row.timestamp <= last]
    candidate = staging.prepare(configured_transformer, record.semantic_record(),
                                [row.semantic_record() for row in history])
    if candidate.outcome in ('CONFLICT','REJECTED_LATE_OBSERVATION'):
        return None, candidate.outcome
    try:
        result = validate_result_identity(parse_ml_result(candidate.result), record)
    except Exception:
        staging.discard(candidate)
        raise
    branch['candidate'] = candidate
    branch['transformer'] = configured_transformer
    processing_repo.save_checkpoint(session, asset, candidate.checkpoint)
    return result, candidate.outcome


@event.listens_for(Session, 'after_commit')
def committed(session):
    if session.in_nested_transaction():
        return
    context = session.info.get(KEY)
    if context is not None:
        context['committed'] = True


@event.listens_for(Session, 'after_rollback')
def rolled_back(session):
    if not session.in_nested_transaction():
        context = session.info.get(KEY)
        if context is not None:
            context['committed'] = False


@event.listens_for(Session, 'after_transaction_end')
def finish(session, transaction):
    if transaction.parent is not None:
        return
    session.info.pop('h02_pending_receipts', None)
    context = session.info.pop(KEY, None)
    if context is None:
        return
    try:
        installed_assets = set()
        for asset, branch in context['branches'].items():
            runtime, candidate = branch['runtime'], branch['candidate']
            if context['committed']:
                try:
                    if candidate is not None:
                        runtime.install(candidate, database_committed=True)
                    checkpoint = runtime.export_checkpoint(asset)
                    if checkpoint is not None:
                        branch['owner'].import_checkpoint(checkpoint, branch['transformer'])
                        installed_assets.add(asset)
                except Exception:
                    # SQL is already committed. On the next transaction, read
                    # the durable checkpoint before preparing again.
                    logger.error('ML install failed after SQL commit asset=%s; database restore required', asset)
            elif candidate is not None:
                runtime.discard(candidate)
        if context['committed']:
            from app.services import ingestion_diagnostics
            for result in context['results']:
                result.forward_state_advanced = context.get('forward_results', {}).get(id(result)) in installed_assets
                ingestion_diagnostics.increment('exact_retries' if result.duplicate else 'committed')
                if result.ingestion_outcome == 'REJECTED_LATE_OBSERVATION':
                    ingestion_diagnostics.increment('late')
                if result.analytics is None:
                    ingestion_diagnostics.increment('ml_unavailable')
    finally:
        for lock in reversed(list(context['locks'].values())):
            lock.release()
