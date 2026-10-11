from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_logging import RequestLoggingMiddleware
from app.ml_client.factory import close_ml_client


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.started = False
    consumer = None
    lease = None
    try:
        if get_settings().ml_backend == 'python':
            from app.services.runtime_lease import RuntimeLease
            lease = RuntimeLease()
            await run_in_threadpool(lease.acquire)
        if get_settings().mqtt_enabled:
            from app.mqtt.consumer import MqttConsumer

            consumer = MqttConsumer()
            application.state.mqtt_consumer = consumer
            consumer.start()
        application.state.started = True
        yield
    finally:
        application.state.started = False
        try:
            if consumer is not None:
                await run_in_threadpool(consumer.stop)
        finally:
            close_ml_client()
            if lease is not None:
                await run_in_threadpool(lease.close)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Transformer Digital Twin API",
        version=settings.schema_version,
        lifespan=lifespan,
        description="Canonical telemetry, analytics, proxy risk (alarm/trip-based prediction), "
        "alerts and maintenance for transformer digital twins.",
        contact={"name": "Backend team (placeholder)"},
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(v1_router, prefix="/api/v1")
    return application


app = create_app()
