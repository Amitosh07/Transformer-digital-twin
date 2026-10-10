"""Demo reset and reporting; telemetry ingestion stays in the existing service."""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Alert, Analytics, IngestionRun, MaintenanceRecord, Telemetry, Transformer


def delete_demo_data(session: Session, include_transformers: bool) -> dict[str, int]:
    models = [MaintenanceRecord, Alert, Analytics, Telemetry, IngestionRun]
    if include_transformers:
        models.append(Transformer)
    counts = {}
    for model in models:
        counts[model.__tablename__] = session.execute(delete(model)).rowcount
    return counts


def summary(session: Session, asset: str) -> dict[str, Any]:
    counts = {
        model.__tablename__: session.scalar(
            select(func.count()).select_from(model).where(model.transformer_id == asset)
        )
        or 0
        for model in (Telemetry, Analytics, Alert, MaintenanceRecord)
    }
    scenarios = dict(
        session.execute(
            select(Telemetry.scenario_id, func.count())
            .where(Telemetry.transformer_id == asset)
            .group_by(Telemetry.scenario_id)
        ).all()
    )
    low, high = session.execute(
        select(func.min(Analytics.health_index), func.max(Analytics.health_index)).where(
            Analytics.transformer_id == asset
        )
    ).one()
    return counts | {"scenarios": scenarios, "health_index_min": low, "health_index_max": high}
