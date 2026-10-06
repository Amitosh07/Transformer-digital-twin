from fastapi import APIRouter

from app.api.v1.simulate import router as simulate_router
from app.api.v1.telemetry import router as telemetry_router

router = APIRouter()
router.include_router(telemetry_router)
router.include_router(simulate_router)
