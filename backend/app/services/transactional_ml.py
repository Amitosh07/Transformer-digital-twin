"""Transaction-private H01 sessions; public memory changes only after SQL commit.

Intermediate batch checkpoints hydrate PRIVATE speculative branches, never the
committed owner. The final candidate is installed after the actual commit.
"""
import logging
from threading import RLock, Lock
from time import perf_counter
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
    profile_start = perf_counter()
    reused = False
    branch = context['branches'].get(asset)
    if branch is None:
        revision = processing_repo.checkpoint_revision(session, asset)
        cache = getattr(owner, '_backend_verified_checkpoints', {}).get(asset)
        same_revision = revision is not None and cache is not None and cache.get('revision') == revision
        saved = cache['checkpoint'] if same_revision else processing_repo.checkpoint(session, asset)
        state = owner.pipeline._asset_states.get(asset)
        reusable = (saved is not None and cache is not None and cache['checkpoint'] == saved
                    and cache['transformer'] == configured_transformer and state is cache['state']
                    and state.last_payload_hash == saved['last_payload_hash']
                    and saved['state']['coverage']['payload']['bundle_configuration_fingerprint'] == owner.pipeline.bundle.configuration_fingerprint)
        reused = reusable
        staging = owner if reusable else PipelineSession(UnifiedMLPipeline(owner.pipeline.bundle))
        if saved is not None and not reusable:
            # Database is authoritative after a commit/install crash, including
            # failed restore quarantine. Do not invent a clean protection state.
            staging.import_checkpoint(saved, configured_transformer)
        branch = {'runtime': staging, 'owner': owner, 'candidate': None, 'checkpoint': saved,
                  'transformer': configured_transformer}
        context['branches'][asset] = branch
    staging = branch['runtime']
    previous = branch['candidate']
    if previous is not None:
        # The previous SQL writes are still uncommitted. This private branch is
        # speculative state for the next sample; never a public committed owner.
        staging.discard(previous)
        if staging is owner:
            # Batch speculation must never install intermediate state in the owner.
            staging = PipelineSession(UnifiedMLPipeline(owner.pipeline.bundle))
            branch['runtime'] = staging
        staging.import_checkpoint(previous.checkpoint, branch['transformer'])
        branch['checkpoint'] = previous.checkpoint
        branch['candidate'] = None
    # The imported durable/speculative checkpoint already describes this state.
    # Exporting all history and identity results again just to read one timestamp
    # costs megabytes of serialization per observation.
    committed_checkpoint = branch['checkpoint']
    if history is None:
        # Fully validated durable checkpoints already contain causal history.
        # SQL rows hydrate genuinely cold state; explicit supplied history still
        # receives the existing H01 consistency validation below.
        if committed_checkpoint is None:
            from app.repositories import telemetry_repo
            from app.core.config import get_settings
            history = telemetry_repo.load_history(session, asset, record.timestamp,
                                                  get_settings().ml_history_window)
        else:
            history = []
    if committed_checkpoint is not None:
        from datetime import datetime
        last = datetime.fromisoformat(committed_checkpoint['committed_event_time'].replace('Z', '+00:00'))
        # Accepted-but-unanalysed rows are not forward state. Do not replay them
        # implicitly after an outage; the current observation exposes the gap.
        history = [row for row in history if row.timestamp <= last]
    profile_restored = perf_counter()
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
    profile_prepared = perf_counter()
    branch['revision'] = processing_repo.save_checkpoint(session, asset, candidate.checkpoint)
    samples = getattr(owner, '_backend_profile', [])
    samples.append((profile_restored - profile_start, profile_prepared - profile_restored,
                    perf_counter() - profile_prepared, int(reused)))
    if len(samples) >= 100:
        logger.info('H07 ML timing samples=%s restore_read_mean=%.4f prepare_mean=%.4f checkpoint_sql_mean=%.4f owner_reuse=%s',
                    len(samples), *(sum(row[i] for row in samples)/len(samples) for i in range(3)),
                    sum(row[3] for row in samples))
        samples.clear()
    owner._backend_profile = samples
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
                    # Install does not alter checkpoint content. Transfer the exact
                    # persisted candidate, preserving DB-authoritative recovery.
                    checkpoint = candidate.checkpoint if candidate is not None else branch['checkpoint']
                    if checkpoint is not None:
                        if runtime is not branch['owner']:
                            branch['owner'].import_checkpoint(checkpoint, branch['transformer'])
                        owner = branch['owner']
                        if not hasattr(owner, '_backend_verified_checkpoints'):
                            owner._backend_verified_checkpoints = {}
                        owner._backend_verified_checkpoints[asset] = {
                            'checkpoint': checkpoint, 'transformer': branch['transformer'],
                            'state': owner.pipeline._asset_states.get(asset), 'revision': branch.get('revision')}
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
