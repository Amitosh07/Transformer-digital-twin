from fastapi import APIRouter

from app.api.v1.alerts_read import router as alerts_read_router
from app.api.v1.alerts_write import router as alerts_write_router
from app.api.v1.history import router as history_router
from app.api.v1.latest import router as latest_router
from app.api.v1.maintenance_read import router as maintenance_read_router
from app.api.v1.mqtt_status import router as mqtt_status_router
from app.api.v1.simulate import router as simulate_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.transformers import router as transformers_router

router = APIRouter()
router.include_router(telemetry_router)
router.include_router(simulate_router)
router.include_router(mqtt_status_router)
router.include_router(transformers_router)
router.include_router(latest_router)
router.include_router(history_router)
router.include_router(alerts_read_router)
router.include_router(maintenance_read_router)
router.include_router(alerts_write_router)
