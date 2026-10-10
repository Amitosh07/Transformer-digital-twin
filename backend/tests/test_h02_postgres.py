"""H02 SQL acceptance gates. Only the disposable PostgreSQL fixture is allowed."""
import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, inspect
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.ml_client.python_client import PythonMLTwinClient
from app.models import Telemetry, Analytics, Alert, MaintenanceRecord
from app.models.processing import MLCheckpoint, IngestionReceipt
from app.repositories import telemetry_repo
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerIn, TransformerPatch
from app.services import ingestion_service as service, query_service
from app.api.v1.receipts import get_receipt
from app.schemas.query import TimeWindow, Pagination
from tests.test_h02_contracts import example

pytestmark = pytest.mark.postgres


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv('ML_RUNTIME_MODE', 'DEMO_UNVERIFIED_CONFIG')
    client = PythonMLTwinClient(Settings(_env_file=None, ml_backend='python',
                                         ml_python_entrypoint='ml.pipeline:analyze'))
    monkeypatch.setattr(service, 'get_ml_client', lambda: client)
    return client


def record(asset, seconds=0, **changes):
    return TelemetryIn.model_validate({'transformer_id': asset,
        'timestamp': (datetime(2026,10,9,tzinfo=UTC)+timedelta(seconds=seconds)).isoformat(),
        'oil_temperature': 42, 'oil_level': 8, 'oil_temp_trip': 0} | changes)


def count(session, model, asset):
    return session.scalar(select(func.count()).select_from(model).where(model.transformer_id == asset))


def effects(session, asset):
    return {model.__tablename__: [tuple(getattr(row, column.key) for column in model.__table__.columns)
        for row in session.scalars(select(model).where(model.transformer_id == asset).order_by(model.id))]
        for model in (Alert, MaintenanceRecord)}


def test_receipt_visibility_duplicate_conflict_and_late(db_engine, runtime):
    asset = 'H02-' + uuid4().hex
    # Registered asset must be durable before the independent visibility read.
    with Session(db_engine) as setup:
        query_service.create_transformer(setup, TransformerIn(id=asset, name=asset))
    with Session(db_engine, expire_on_commit=False) as write:
        prepared = service.ingest_record(write, record(asset), _commit=False)
        assert prepared.forward_state_advanced is False
        assert get_receipt(write, prepared.snapshot_id).status_code == 404
        with Session(db_engine) as read:
            assert read.get(IngestionReceipt, prepared.snapshot_id) is None
        assert runtime.transactional_runtime().export_checkpoint(asset) is None
        write.commit()
        assert prepared.forward_state_advanced is True
        assert get_receipt(write, prepared.snapshot_id)['receipt_status'] == 'COMMITTED'
        checkpoint = copy.deepcopy(write.get(MLCheckpoint, asset).checkpoint)
        before_effects = copy.deepcopy(effects(write, asset))
        result = service.ingest_record(write, record(asset))
        assert result.duplicate and result.analytics == prepared.analytics
        assert result.forward_state_advanced is False
        assert effects(write, asset) == before_effects
        assert count(write, Telemetry, asset) == count(write, Analytics, asset) == 1
        with pytest.raises(HTTPException) as conflict:
            service.ingest_record(write, record(asset, oil_temp_trip=1))
        assert conflict.value.status_code == 409
        write.expire_all()
        assert write.get(MLCheckpoint, asset).checkpoint == checkpoint
        assert runtime.transactional_runtime().export_checkpoint(asset) == checkpoint
        assert count(write, Telemetry, asset) == 1
        assert effects(write, asset) == before_effects
        assert write.scalar(select(Telemetry).where(Telemetry.transformer_id == asset)).oil_temp_trip == 0
        conflict_hash = service.digest(record(asset, oil_temp_trip=1))
        assert get_receipt(write, conflict_hash)['receipt_status'] == 'CONFLICT'
        service.ingest_record(write, record(asset, 10))
        before = runtime.transactional_runtime().export_checkpoint(asset)
        late = service.ingest_record(write, record(asset, 5))
        assert late.ingestion_outcome == 'REJECTED_LATE_OBSERVATION'
        assert get_receipt(write, late.snapshot_id).status_code == 404
        assert runtime.transactional_runtime().export_checkpoint(asset) == before


def test_rollback_after_inference_and_restart_restore(db_engine, runtime, monkeypatch):
    asset = 'H02-' + uuid4().hex
    real_hook = service.hooks.evaluate_alerts
    def fail(*args):
        raise RuntimeError('Injected persistence effect failure')
    with Session(db_engine, expire_on_commit=False) as session:
        monkeypatch.setattr(service.hooks, 'evaluate_alerts', fail)
        with pytest.raises(RuntimeError):
            service.ingest_record(session, record(asset, oil_temp_trip=1))
        assert runtime.transactional_runtime().export_checkpoint(asset) is None
        assert count(session, Telemetry, asset) == 0
        monkeypatch.setattr(service.hooks, 'evaluate_alerts', real_hook)
        service.ingest_record(session, record(asset, oil_temp_trip=1))
        assert count(session, Telemetry, asset) == 1
        replacement = PythonMLTwinClient(runtime.settings)
        monkeypatch.setattr(service, 'get_ml_client', lambda: replacement)
        next_result = service.ingest_record(session, record(asset, 5))
        assert next_result.analytics.metadata.maintenance_trip_latched is True
        before = replacement.transactional_runtime().export_checkpoint(asset)
        checkpoint = session.get(MLCheckpoint, asset)
        corrupt = copy.deepcopy(checkpoint.checkpoint)
        corrupt['checkpoint_version'] = 'incompatible'
        checkpoint.checkpoint = corrupt
        session.commit()
        unavailable = service.ingest_record(session, record(asset, 10))
        assert unavailable.analytics is None
        assert replacement.transactional_runtime().export_checkpoint(asset) == before
        latest = query_service.latest(session, asset)
        assert latest.analytics is None and latest.analytics_availability.state_coverage_loss
        assert 'CHECKPOINT_RESTORE_FAILED' in latest.analytics_availability.reasons


def test_registry_acquisition_metadata_round_trip(db_engine, runtime):
    asset = 'H02-' + uuid4().hex
    raw_asset = example('asset-valid') | {'id': asset}
    raw_record = example('telemetry-valid') | {'transformer_id': asset}
    with Session(db_engine, expire_on_commit=False) as session:
        created = query_service.create_transformer(session, TransformerIn.model_validate(raw_asset))
        assert created.configuration_metadata.status == 'SYNTHETIC_CONFIG'
        cleared = query_service.patch_transformer(session, asset, TransformerPatch(rated_frequency_hz=None))
        assert cleared.rated_frequency_hz is None
        service.ingest_record(session, TelemetryIn.model_validate(raw_record))
        latest = query_service.latest(session, asset).model_dump(mode='json')
        assert latest['telemetry']['acquisition'] == raw_record['acquisition']
        assert latest['analytics']['metadata']['versions']['bundle_id']
        assert latest['analytics']['timestamp'] == latest['telemetry']['timestamp']
        window = TimeWindow(from_time='2026-10-08T23:59:59Z', to_time='2026-10-09T00:00:01Z')
        history = query_service.telemetry(session, asset, window, Pagination(limit=10, offset=0), 'asc', None)
        assert history.items[0].acquisition == TelemetryIn.model_validate(raw_record).acquisition
        assert query_service.analytics(session, asset, window, Pagination(limit=10, offset=0), 'asc').items[0].metadata is not None


def test_batch_rollback_retry_and_asset_isolation(db_engine, runtime, monkeypatch):
    a, b = 'H02-'+uuid4().hex, 'H02-'+uuid4().hex
    rows = [record(a, oil_temp_trip=1).semantic_record(), record(a, 5).semantic_record(), record(b).semantic_record()]
    real_hook = service.hooks.evaluate_alerts
    calls = 0
    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Injected batch rollback')
        return real_hook(*args)
    with Session(db_engine, expire_on_commit=False) as session:
        monkeypatch.setattr(service.hooks, 'evaluate_alerts', fail_second)
        with pytest.raises(RuntimeError):
            service.ingest_batch(session, rows)
        assert count(session, Telemetry, a) == 0
        assert runtime.transactional_runtime().export_checkpoint(a) is None
        monkeypatch.setattr(service.hooks, 'evaluate_alerts', real_hook)
        summary = service.ingest_batch(session, rows)
        assert summary.inserted_count == 3
        assert service.ingest_batch(session, rows).duplicate_count == 3
        assert count(session, Analytics, a) == 2
        assert query_service.latest(session, a).analytics.metadata.maintenance_trip_latched is True
        assert query_service.latest(session, b).analytics.metadata.maintenance_trip_latched is False


def test_new_migration_schema_and_legacy_hash_comparison(db_engine, runtime):
    columns = {column['name'] for column in inspect(db_engine).get_columns('telemetry')}
    assert {'acquisition', 'payload_hash', 'semantic_payload', 'ml_status'} <= columns
    assert {'ingestion_receipts', 'ml_checkpoints'} <= set(inspect(db_engine).get_table_names())
    asset = 'H02-'+uuid4().hex
    with Session(db_engine, expire_on_commit=False) as session:
        query_service.create_transformer(session, TransformerIn(id=asset, name=asset))
        old = Telemetry(**record(asset).model_dump(exclude={'acquisition'}),
                        is_missing_critical=True, data_quality_score=0)
        session.add(old)
        session.commit()
        assert service.ingest_record(session, record(asset)).duplicate
        with pytest.raises(HTTPException) as caught:
            service.ingest_record(session, record(asset, oil_temp_trip=1))
        assert caught.value.status_code == 409


def test_one_hour_history_and_boundary_are_restorable(db_engine):
    asset = 'H02-' + uuid4().hex
    with Session(db_engine, expire_on_commit=False) as session:
        query_service.create_transformer(session, TransformerIn(id=asset, name=asset))
        # Storage query test: no need to run hundreds of model inferences.
        for seconds in range(-5, 3605, 5):
            session.add(Telemetry(**record(asset, seconds).model_dump(exclude={'acquisition'}),
                                  is_missing_critical=True, data_quality_score=0))
        session.commit()
        history = telemetry_repo.load_history(session, asset,
            datetime(2026,10,9,tzinfo=UTC)+timedelta(hours=1), 4096)
        assert len(history) == 721
        assert history[0].timestamp == datetime(2026,10,9,tzinfo=UTC)-timedelta(seconds=5)
        assert len(telemetry_repo.load_history(session, asset,
            datetime(2026,10,9,tzinfo=UTC)+timedelta(hours=1), 60)) == 60


def test_checkpoint_revision_reuses_owner_but_detects_content_edit(db_engine, runtime, monkeypatch):
    from app.repositories import processing_repo
    from sqlalchemy import update
    asset = 'H07-revision-' + uuid4().hex
    with Session(db_engine, expire_on_commit=False) as db:
        service.ingest_record(db, record(asset, oil_temp_trip=1))
        original = processing_repo.checkpoint
        monkeypatch.setattr(processing_repo, 'checkpoint', lambda *_: (_ for _ in ()).throw(AssertionError('Warm checkpoint must not transfer full JSON')))
        result = service.ingest_record(db, record(asset, seconds=5))
        assert result.analytics is not None and result.forward_state_advanced
        monkeypatch.setattr(processing_repo, 'checkpoint', original)
        committed = runtime.transactional_runtime().export_checkpoint(asset)
        before_revision = processing_repo.checkpoint_revision(db, asset)
        corrupted = copy.deepcopy(committed)
        corrupted['state']['history']['payload']['records'][-1]['oil_temp_trip'] = 1
        db.execute(update(MLCheckpoint).where(MLCheckpoint.transformer_id==asset).values(checkpoint=corrupted))
        db.commit()
        assert processing_repo.checkpoint_revision(db, asset) != before_revision
        result = service.ingest_record(db, record(asset, seconds=10))
        assert result.analytics is None and not result.forward_state_advanced
        assert runtime.transactional_runtime().export_checkpoint(asset) == committed
        assert committed['state']['maintenance_persistence']['payload']['trip_latched']
