"""Failure isolation for ingestion; ML failures must never discard telemetry."""

import logging

import httpx

from app.core.config import Settings, get_settings
from app.ml_client.base import (
    MLTimeoutError,
    MLTwinClient,
    parse_ml_result,
    validate_result_identity,
)
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut

logger = logging.getLogger(__name__)


def safe_analyze(
    client: MLTwinClient,
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
) -> MLResultIn:
    try:
        result = parse_ml_result(client.analyze(transformer, record, history))
        return validate_result_identity(result, record)
    except Exception as exc:
        logger.error(
            "ML analysis failed transformer_id=%s timestamp=%s error_type=%s",
            record.transformer_id,
            record.timestamp.isoformat(),
            type(exc).__name__,
        )
        message = (
            "ML analysis timed out"
            if isinstance(exc, (MLTimeoutError, TimeoutError, httpx.TimeoutException))
            else "ML analysis failed"
        )
        try:
            schema_version = get_settings().schema_version
        except Exception:
            # Keep failure isolation even if settings cannot be loaded during an error.
            schema_version = Settings.model_fields["schema_version"].default
        return MLResultIn(
            transformer_id=record.transformer_id,
            timestamp=record.timestamp,
            inference_status="INSUFFICIENT_DATA",
            error_detail=message,
            schema_version=schema_version,
            feature_version="unavailable",
            model_version="unavailable",
        )
