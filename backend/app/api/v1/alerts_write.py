"""Thin alert lifecycle and maintenance mutation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.v1.read_examples import ALERT, MAINTENANCE, TIME, response_example
from app.db.session import DatabaseSession
from app.schemas.alert import AlertOut
from app.schemas.common import ErrorResponse
from app.schemas.maintenance import MaintenanceOut, MaintenancePatch
from app.services import alert_service, maintenance_service

router = APIRouter()
Id = Annotated[int, Path(gt=0)]
ALERT_RESPONSES = response_example(ALERT) | {
    404: {"model": ErrorResponse, "description": "Alert not found"},
    409: {"model": ErrorResponse, "description": "Invalid alert transition"},
}
MAINTENANCE_RESPONSES = response_example(MAINTENANCE) | {
    404: {"model": ErrorResponse, "description": "Maintenance record not found"},
    409: {"model": ErrorResponse, "description": "Record is no longer OPEN"},
}


@router.get("/alerts/{id}", response_model=AlertOut, tags=["alerts"], responses=ALERT_RESPONSES)
def get_alert(id: Id, db: DatabaseSession) -> AlertOut:
    return alert_service.get_alert(db, id)


@router.patch(
    "/alerts/{id}/acknowledge",
    response_model=AlertOut,
    tags=["alerts"],
    responses=ALERT_RESPONSES
    | response_example(ALERT | {"status": "ACKNOWLEDGED", "acknowledged_at": TIME})
    | {404: {"model": ErrorResponse, "description": "Alert not found"}},
)
def acknowledge_alert(id: Id, db: DatabaseSession) -> AlertOut:
    return alert_service.transition(db, id, "acknowledge")


@router.patch(
    "/alerts/{id}/resolve",
    response_model=AlertOut,
    tags=["alerts"],
    responses=ALERT_RESPONSES
    | response_example(ALERT | {"status": "RESOLVED", "resolved_at": TIME})
    | {404: {"model": ErrorResponse, "description": "Alert not found"}},
)
def resolve_alert(id: Id, db: DatabaseSession) -> AlertOut:
    return alert_service.transition(db, id, "resolve")


@router.get(
    "/maintenance/{id}",
    response_model=MaintenanceOut,
    tags=["maintenance"],
    responses=MAINTENANCE_RESPONSES,
)
def get_maintenance(id: Id, db: DatabaseSession) -> MaintenanceOut:
    return maintenance_service.get_record(db, id)


@router.patch(
    "/maintenance/{id}",
    response_model=MaintenanceOut,
    tags=["maintenance"],
    responses=MAINTENANCE_RESPONSES
    | response_example(MAINTENANCE | {"status": "DONE"})
    | {404: {"model": ErrorResponse, "description": "Maintenance record not found"}},
)
def patch_maintenance(id: Id, payload: MaintenancePatch, db: DatabaseSession) -> MaintenanceOut:
    return maintenance_service.complete(db, id, payload)
