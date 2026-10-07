from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.db.session import DatabaseSession
from app.schemas.ingestion import IngestionSummary, RawTelemetryBatchIn
from app.schemas.telemetry import TelemetryIn
from app.services.ingestion_service import ingest_batch, ingest_record

router = APIRouter(tags=["telemetry"])


@router.post("/telemetry", status_code=201)
def post_telemetry(
    record: TelemetryIn,
    db: DatabaseSession,
    run_ml: Annotated[bool, Query()] = True,
) -> JSONResponse:
    result = ingest_record(db, record, run_ml=run_ml)
    if result.duplicate:
        return JSONResponse(
            status_code=200, content={"duplicate": True, "telemetry_id": result.telemetry_id}
        )
    return JSONResponse(
        status_code=201, content=result.model_dump(mode="json", exclude={"duplicate"})
    )


@router.post("/telemetry/batch", response_model=IngestionSummary)
def post_batch(
    payload: RawTelemetryBatchIn,
    db: DatabaseSession,
    run_ml: Annotated[bool, Query()] = True,
    source_name: Annotated[str, Query(min_length=1, max_length=255)] = "api",
) -> IngestionSummary:
    return ingest_batch(db, payload.records, run_ml=run_ml, source_name=source_name)
