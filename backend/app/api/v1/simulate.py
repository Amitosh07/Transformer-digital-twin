from fastapi import APIRouter, BackgroundTasks

from app.db.session import DatabaseSession
from app.schemas.ingestion import ReplayAccepted, ReplayIn, ReplayStatusOut
from app.services.replay_service import get_replay_status, run_replay, start_replay

router = APIRouter(tags=["simulation"])


@router.post("/simulate/replay", status_code=202, response_model=ReplayAccepted)
def replay(
    request: ReplayIn, background_tasks: BackgroundTasks, db: DatabaseSession
) -> ReplayAccepted:
    run_id = start_replay(db, request)
    background_tasks.add_task(run_replay, run_id, request)
    return ReplayAccepted(run_id=run_id)


@router.get("/simulate/replay/{run_id}", response_model=ReplayStatusOut)
def replay_status(run_id: int, db: DatabaseSession) -> ReplayStatusOut:
    return get_replay_status(db, run_id)
