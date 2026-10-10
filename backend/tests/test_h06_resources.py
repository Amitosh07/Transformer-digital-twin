"""Actual PostgreSQL/API H06 resources with installed H01 runtime."""
import json
from pathlib import Path
from datetime import datetime,UTC,timedelta
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.ml_client.python_client import PythonMLTwinClient
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerIn
from app.schemas.query import TimeWindow
from app.services import query_service,ingestion_service,analytics_resources
from tests.test_h02_contracts import example

@pytest.mark.postgres
def test_persisted_rul_energy_checkpoint_projection_and_retry(db_engine,monkeypatch,tmp_path):
    asset='H06-'+uuid4().hex
    scenario=dict(scenario_id='h06-test',version='fictional-h06-test-v1',start_time='2026-10-09T00:00:00Z',initial_degradation=.2,endpoint=1,rate_per_hour=.01,horizon_hours=100,maximum_gap_seconds=7200,assume_constant_rate_across_gaps=False)
    path=tmp_path/'policy.json';path.write_text(json.dumps(dict(version='h06-policy-v1',assets={asset:dict(synthetic_rul=scenario,energy=dict(version='h06-test-energy-v1',method='POWER',maximum_gap_seconds=7200,power_sign='IMPORT_ONLY_NONNEGATIVE'))})))
    settings=Settings(_env_file=None,ml_backend='python',ml_python_entrypoint='ml.pipeline:analyze',analytics_policy_file=str(path))
    monkeypatch.setattr(analytics_resources,'get_settings',lambda:settings)
    monkeypatch.setenv('ML_RUNTIME_MODE','DEMO_UNVERIFIED_CONFIG')
    runtime=PythonMLTwinClient(settings);monkeypatch.setattr(ingestion_service,'get_ml_client',lambda:runtime)
    registration=example('asset-valid');registration['id']=asset
    def record(seconds):
        value=example('telemetry-valid');value.update(transformer_id=asset,timestamp=(datetime(2026,10,9,tzinfo=UTC)+timedelta(seconds=seconds)).isoformat(),active_power_total=10)
        value['acquisition']['snapshot_id']=None
        return TelemetryIn.model_validate(value)
    with Session(db_engine,expire_on_commit=False) as db:
        query_service.create_transformer(db,TransformerIn.model_validate(registration))
        first=ingestion_service.ingest_record(db,record(0))
        assert analytics_resources.rul(db,asset)['rul']['rul_value']==80
        assert analytics_resources.projection(db,asset)['projected_curve'][-1]['degradation']==1
        ingestion_service.ingest_record(db,record(7200))
        result=analytics_resources.energy(db,asset,TimeWindow(from_time=datetime(2026,10,9,tzinfo=UTC),to_time=datetime(2026,10,9,2,tzinfo=UTC)),'1h')
        assert result['consumed_kwh']==20 and result['loss_kw'] is None
        before=runtime.transactional_runtime().export_checkpoint(asset)
        retry=ingestion_service.ingest_record(db,record(7200));assert retry.duplicate
        assert runtime.transactional_runtime().export_checkpoint(asset)==before
        assert analytics_resources.rul(db,asset)['rul']['rul_value']==pytest.approx(78)
