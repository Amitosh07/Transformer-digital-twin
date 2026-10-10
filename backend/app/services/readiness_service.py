"""Readiness checks are independent of telemetry ingestion and ML inference."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ml_client.factory import get_ml_client
from app.ml_client.http_client import HttpMLTwinClient
from app.ml_client.python_client import PythonMLTwinClient
from app.repositories import readiness_repo
from app.schemas.readiness import ReadinessOut


def check_ready(session: Session, settings: Settings, started: bool) -> ReadinessOut:
    result = ReadinessOut(
        status="not_ready",
        db="error",
        migrations="error",
        ml="ready" if settings.ml_backend == "stub" else "error",
    )
    if not started:
        result.details["startup"] = "Service is starting or stopping"
        return result
    try:
        migrated = readiness_repo.check(session)
        result.db = "ready"
        result.migrations = "ready" if migrated else "error"
        if not migrated:
            result.details["migrations"] = "Database revisions do not match migration heads"
    except Exception:
        result.details["db"] = "Database readiness check failed"
    if settings.ml_backend == "stub":
        result.ml = "ready"
    else:
        try:
            client = get_ml_client()
            if settings.ml_backend == "python" and isinstance(client, PythonMLTwinClient):
                client.check_importable()
                bundle = client.transactional_runtime().pipeline.bundle
                result.ml = "ready"
                result.details['ml'] = (f'{bundle.runtime_mode}; configuration={bundle.configuration_readiness}; '
                                        'operational forecast release remains gated')
            elif settings.ml_backend == "http" and isinstance(client, HttpMLTwinClient):
                result.ml = client.probe()
                if result.ml == "unchecked":
                    result.details["ml"] = "ML service does not support HEAD or GET probes"
                elif result.ml == "error":
                    result.details["ml"] = "ML service readiness probe failed"
            else:
                result.details["ml"] = "ML client configuration mismatch"
        except Exception:
            result.details["ml"] = "ML client readiness check failed"
    if result.db == result.migrations == "ready" and result.ml in ("ready", "unchecked"):
        result.status = "ready"
    return result
