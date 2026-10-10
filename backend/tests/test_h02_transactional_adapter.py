"""Adapter unit evidence with real H01 candidates; NOT PostgreSQL evidence."""
import copy
from types import SimpleNamespace
from unittest.mock import Mock
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.ml_client.python_client import PythonMLTwinClient
from app.schemas.transformer import TransformerOut
from app.schemas.telemetry import TelemetryIn
from app.services import transactional_ml as adapter
from app.repositories import processing_repo


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setenv('ML_RUNTIME_MODE', 'DEMO_UNVERIFIED_CONFIG')
    client = PythonMLTwinClient(Settings(_env_file=None, ml_backend='python',
                                         ml_python_entrypoint='ml.pipeline:analyze'))
    stored = {}
    monkeypatch.setattr(processing_repo, 'checkpoint_revision', lambda session, asset: None)
    monkeypatch.setattr(processing_repo, 'checkpoint', lambda session, asset: copy.deepcopy(stored.get(asset)))
    monkeypatch.setattr(processing_repo, 'save_checkpoint', lambda session, asset, value: stored.update({asset: copy.deepcopy(value)}))
    return client, stored


def asset(identifier='adapter'):
    now = datetime(2026, 10, 9, tzinfo=UTC)
    return TransformerOut(id=identifier, name=identifier, created_at=now, updated_at=now)


def record(identifier='adapter', seconds=0, trip=0):
    return TelemetryIn(transformer_id=identifier,
        timestamp=datetime(2026,10,9,tzinfo=UTC)+timedelta(seconds=seconds),
        oil_temperature=42, oil_level=8, oil_temp_trip=trip)


def finish(session, success):
    session.info[adapter.KEY]['committed'] = success
    adapter.finish(session, SimpleNamespace(parent=None))


def test_rollback_discards_real_candidate_and_commit_installs_once(context):
    client, stored = context
    with Session() as session:
        adapter.lock_assets(session, ['adapter'])
        result, outcome = adapter.prepare(session, client, asset(), record(), [])
        assert result.metadata is not None and result.fault_risk is None
        assert outcome == 'ACCEPTED'
        assert client.transactional_runtime().export_checkpoint('adapter') is None
        finish(session, False)
        assert client.transactional_runtime().export_checkpoint('adapter') is None
        # Fake persistence rolls back independently in this unit harness.
        stored.clear()
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(), [])
        finish(session, True)
        checkpoint = client.transactional_runtime().export_checkpoint('adapter')
        assert checkpoint == stored['adapter']
        adapter.lock_assets(session, ['adapter'])
        duplicate, outcome = adapter.prepare(session, client, asset(), record(), [])
        assert outcome == 'EXACT_RETRY'
        finish(session, True)
        assert client.transactional_runtime().export_checkpoint('adapter') == checkpoint


def test_batch_speculation_does_not_mutate_owner_and_restores(context):
    client, stored = context
    with Session() as session:
        adapter.lock_assets(session, ['a', 'b'])
        adapter.prepare(session, client, asset('a'), record('a', trip=1), [])
        adapter.prepare(session, client, asset('a'), record('a', seconds=5), [])
        adapter.prepare(session, client, asset('b'), record('b'), [])
        assert client.transactional_runtime().export_checkpoint('a') is None
        finish(session, True)
        assert client.transactional_runtime().export_checkpoint('a') == stored['a']
        assert client.transactional_runtime().export_checkpoint('b') == stored['b']
        replacement = PythonMLTwinClient(client.settings)
        adapter.lock_assets(session, ['a'])
        restored, outcome = adapter.prepare(session, replacement, asset('a'), record('a', 10), [])
        assert outcome == 'ACCEPTED'
        assert restored.metadata.maintenance_trip_latched is True
        finish(session, True)


def test_corrupt_checkpoint_is_rejected_without_clear_owner(context):
    client, stored = context
    with Session() as session:
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(trip=1), [])
        finish(session, True)
        before = client.transactional_runtime().export_checkpoint('adapter')
        stored['adapter']['checkpoint_version'] = 'incompatible'
        adapter.lock_assets(session, ['adapter'])
        with pytest.raises(ValueError):
            adapter.prepare(session, client, asset(), record(seconds=5), [])
        finish(session, False)
        assert client.transactional_runtime().export_checkpoint('adapter') == before


def test_adapter_reuses_exact_persisted_checkpoint_without_reexport(context, monkeypatch):
    client, stored = context
    export_owner = client.transactional_runtime().export_checkpoint
    with Session() as session:
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(trip=1), [])
        staging = session.info[adapter.KEY]['branches']['adapter']['runtime']
        monkeypatch.setattr(staging, 'export_checkpoint', lambda *args: pytest.fail('redundant checkpoint export'))
        finish(session, True)
        assert export_owner('adapter') == stored['adapter']
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(seconds=5), [])
        staging = session.info[adapter.KEY]['branches']['adapter']['runtime']
        monkeypatch.setattr(staging, 'export_checkpoint', lambda *args: pytest.fail('redundant checkpoint export'))
        # Batch preparation must use the previous candidate without serializing it again.
        adapter.prepare(session, client, asset(), record(seconds=10), [])
        finish(session, True)
        assert export_owner('adapter') == stored['adapter']
        assert stored['adapter']['state']['maintenance_persistence']['payload']['trip_latched'] is True


def test_runtime_lease_rejects_second_owner(monkeypatch):
    from app.services import runtime_lease
    connection = Mock()
    connection.scalar.return_value = False
    monkeypatch.setattr(runtime_lease, 'get_engine', lambda: SimpleNamespace(connect=lambda: connection))
    with pytest.raises(RuntimeError, match='One Python ML runtime'):
        runtime_lease.RuntimeLease().acquire()
    connection.close.assert_called_once()


def test_verified_owner_reuse_rollback_and_changed_durable_content(context, monkeypatch):
    client, stored = context
    with Session() as session:
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(trip=1), [])
        finish(session, True)
        owner = client.transactional_runtime()
        original = owner.export_checkpoint('adapter')
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(seconds=5), [])
        assert session.info[adapter.KEY]['branches']['adapter']['runtime'] is owner
        finish(session, False)
        assert owner.export_checkpoint('adapter') == original
        stored['adapter'] = original
        stored['adapter']['state']['history']['payload']['records'][0]['oil_temperature'] = 999
        adapter.lock_assets(session, ['adapter'])
        with pytest.raises(ValueError):
            adapter.prepare(session, client, asset(), record(seconds=5), [])
        finish(session, False)


def test_backend_readiness_loads_bundle_not_just_callable(monkeypatch, tmp_path):
    from app.services import readiness_service
    monkeypatch.setattr(readiness_service.readiness_repo, 'check', lambda session: True)
    settings = Settings(_env_file=None, ml_backend='python', ml_python_entrypoint='ml.pipeline:analyze')
    monkeypatch.setenv('ML_RUNTIME_MODE', 'STRICT_FITTED')
    monkeypatch.setenv('ML_ARTIFACT_DIR', str(tmp_path))
    monkeypatch.setattr(readiness_service, 'get_ml_client', lambda: PythonMLTwinClient(settings))
    assert readiness_service.check_ready(None, settings, True).status == 'not_ready'
    monkeypatch.setenv('ML_RUNTIME_MODE', 'DEMO_UNVERIFIED_CONFIG')
    result = readiness_service.check_ready(None, settings, True)
    assert result.status == 'ready'
    assert 'DEMO_UNVERIFIED_CONFIG' in result.details['ml']
    assert 'configuration=UNVERIFIED' in result.details['ml']


def test_sql_history_loaded_only_for_cold_asset(context, monkeypatch):
    from app.repositories import telemetry_repo
    client, stored = context
    calls = []
    def history(*args):
        calls.append(args[1])
        return []
    monkeypatch.setattr(telemetry_repo, 'load_history', history)
    with Session() as session:
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(), None)
        finish(session, True)
        first = client.transactional_runtime().export_checkpoint('adapter')
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, client, asset(), record(seconds=5), None)
        finish(session, False)
        assert calls == ['adapter']
        assert client.transactional_runtime().export_checkpoint('adapter') == first
        stored['adapter'] = copy.deepcopy(first)
        replacement = PythonMLTwinClient(client.settings)
        adapter.lock_assets(session, ['adapter'])
        adapter.prepare(session, replacement, asset(), record(seconds=10), None)
        finish(session, True)
        assert calls == ['adapter']
        assert replacement.transactional_runtime().export_checkpoint('adapter')['observation_count'] == 2
