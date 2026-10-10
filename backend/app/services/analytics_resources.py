"""H06 persisted RUL readers and pure H05 bounded energy orchestration."""
import json
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select
from app.core.config import get_settings
from app.models.analytics import Analytics
from app.models.telemetry import Telemetry
from app.repositories import processing_repo, telemetry_repo
from app.schemas.query import TimeWindow
from app.services.query_service import require_transformer, resolve_window, query_error


def policies(asset):
    path = get_settings().analytics_policy_file
    if not path:
        return {}
    value = json.loads(Path(path).read_text())
    if value.get('version') != 'h06-policy-v1':
        raise ValueError('Unsupported analytics policy version')
    return value.get('assets', {}).get(asset, {})


def runtime_transformer(transformer):
    value = transformer.model_dump(mode='json')
    scenario = policies(transformer.id).get('synthetic_rul')
    if scenario is not None:
        value['synthetic_rul'] = scenario
    return value


def rul(session, asset):
    require_transformer(session, asset)
    row = session.scalar(select(Analytics).where(Analytics.transformer_id == asset,
        Analytics.rul.is_not(None)).order_by(Analytics.timestamp.desc()).limit(1))
    return dict(transformer_id=asset, timestamp=row.timestamp if row else None,
                rul=row.rul if row else None, schema_version='1.1.0')


def projection(session, asset):
    resource = rul(session, asset)
    checkpoint = processing_repo.checkpoint(session, asset)
    curve = []
    if checkpoint and resource['rul']:
        extension = checkpoint['state']['synthetic_degradation'].get('payload')
        from ml.rul.common import event_time
        if extension and event_time(extension['last_event_time']) == event_time(resource['rul']['timestamp']):
            curve = extension['projected_curve']
    return dict(transformer_id=asset, timestamp=resource['timestamp'],
        projected_curve=curve, end_threshold=resource['rul']['end_threshold'] if resource['rul'] else None,
        degradation_unit=resource['rul']['degradation_unit'] if resource['rul'] else None,
        forecast_horizon_hours=resource['rul']['forecast_horizon_hours'] if resource['rul'] else None,
        schema_version='1.1.0')


def energy(session, asset, time: TimeWindow, window):
    from ml.energy import EnergyConfig, LossModel, calculate_energy
    from ml.pipeline import AssetConfig
    from app.schemas.transformer import TransformerOut
    transformer = require_transformer(session, asset)
    durations = {'1h':1,'6h':6,'24h':24,'7d':168}
    bounds = resolve_window(session, asset, time, timedelta(hours=durations[window]))
    policy = policies(asset).get('energy', {})
    # Missing source policy does not assume units, sign or counter semantics.
    config = EnergyConfig(**(dict(version='unconfigured-source', method='POWER',
        maximum_gap_seconds=10, maximum_window_seconds=get_settings().max_window_days*86400) | policy))
    stmt = select(Telemetry).where(Telemetry.transformer_id==asset,
        Telemetry.timestamp>=bounds.start, Telemetry.timestamp<=bounds.end)
    rows = list(session.scalars(stmt.order_by(Telemetry.timestamp).limit(config.maximum_records+1)))
    # Context supports only the policy's explicitly allowed boundary interpolation.
    for condition, order in ((Telemetry.timestamp<bounds.start,Telemetry.timestamp.desc()),
                             (Telemetry.timestamp>bounds.end,Telemetry.timestamp.asc())):
        row = session.scalar(select(Telemetry).where(Telemetry.transformer_id==asset,condition).order_by(order).limit(1))
        if row is not None: rows.append(row)
    if len(rows)>config.maximum_records:
        query_error('window','Energy record cap exceeded; narrow the event-time window')
    cfg = AssetConfig.from_dict(TransformerOut.model_validate(transformer).model_dump(mode='json'))
    records = [telemetry_repo.as_input(row).semantic_record() for row in rows]
    try:
        return calculate_energy(records,asset,bounds.start,bounds.end,config,asset_config=cfg,
            loss_model=LossModel.from_asset(cfg, **policies(asset).get('loss_boundary', {})) if policies(asset).get('loss_boundary') else None)
    except ValueError as exc:
        query_error('window',str(exc))
