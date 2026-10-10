"""Pure maintenance eligibility and caller-owned persistence."""

from dataclasses import dataclass

from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.models.analytics import Analytics
from app.repositories import maintenance_repo, transformer_repo
from app.schemas.analytics import AnalyticsOut, MLResultIn
from app.schemas.common import ReasonCode
from app.schemas.maintenance import MaintenanceOut, MaintenancePatch


@dataclass(frozen=True)
class MaintenanceCandidate:
    priority: str
    reason_codes: list[ReasonCode]
    recommendation: str


def maintenance_candidate(analytics: MLResultIn) -> MaintenanceCandidate | None:
    if analytics.inference_status != "OK" or analytics.maintenance_priority not in (
        "PLAN",
        "URGENT",
    ):
        return None
    return MaintenanceCandidate(
        analytics.maintenance_priority,
        sorted(set(analytics.reason_codes or [])),
        analytics.maintenance_recommendation
        or "Inspect the reported proxy indications using site procedures.",
    )


def evaluate(session: Session, analytics_row: Analytics) -> None:
    candidate = maintenance_candidate(AnalyticsOut.model_validate(analytics_row))
    if candidate is None:
        return
    opened = maintenance_repo.open_records(session, analytics_row.transformer_id)
    if any(
        row.priority == candidate.priority and set(row.reason_codes) == set(candidate.reason_codes)
        for row in opened
    ):
        return
    maintenance_repo.insert_record(
        session,
        {
            "transformer_id": analytics_row.transformer_id,
            "analytics_id": analytics_row.id,
            "timestamp": analytics_row.timestamp,
            "priority": candidate.priority,
            "reason_codes": candidate.reason_codes,
            "recommendation": candidate.recommendation,
            "status": "OPEN",
        },
    )


def get_record(session: Session, record_id: int) -> MaintenanceOut:
    row = maintenance_repo.get(session, record_id)
    if row is None:
        raise HTTPException(404, "Maintenance record not found")
    return MaintenanceOut.model_validate(row)


def complete(session: Session, record_id: int, payload: MaintenancePatch) -> MaintenanceOut:
    row = maintenance_repo.get(session, record_id)
    if row is None:
        raise HTTPException(404, "Maintenance record not found")
    transformer_repo.lock_for_ingestion(session, row.transformer_id)
    row = maintenance_repo.get(session, record_id, lock=True)
    if row is None:
        raise HTTPException(404, "Maintenance record not found")
    if row.status != "OPEN":
        raise HTTPException(409, "Only OPEN maintenance records can change status")
    row.status = payload.status
    session.flush()
    result = MaintenanceOut.model_validate(row)
    session.commit()
    return result
