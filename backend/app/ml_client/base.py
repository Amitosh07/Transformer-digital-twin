"""Public ML boundary; no database, dataframe or feature-engineering dependencies."""

import logging
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut

logger = logging.getLogger(__name__)


class MLClientError(Exception):
    """The ML adapter could not produce a valid result."""


class MLTimeoutError(MLClientError):
    """The ML request exceeded its timeout."""


@runtime_checkable
class MLTwinClient(Protocol):
    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn:
        """Use at most ML_HISTORY_WINDOW prior rows, oldest first, excluding record."""
        ...


def validate_history(
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
    window: int,
) -> None:
    if transformer.id != record.transformer_id:
        raise MLClientError("Transformer and current telemetry identities must match")
    if len(history) > window:
        raise MLClientError("History exceeds ML_HISTORY_WINDOW")
    previous = None
    for row in history:
        if row.transformer_id != record.transformer_id:
            raise MLClientError("History must belong to the current transformer")
        if row.timestamp >= record.timestamp:
            raise MLClientError("History must exclude the current record and future rows")
        if previous is not None and row.timestamp <= previous:
            raise MLClientError("History must be ordered oldest to newest with unique timestamps")
        previous = row.timestamp


def parse_ml_result(value: object) -> MLResultIn:
    if isinstance(value, MLResultIn):
        # Revalidate even models built with model_construct or mutated without validation.
        value = value.model_dump(mode="python", warnings=False)
    if not isinstance(value, Mapping):
        raise MLClientError("ML result must be an object")
    extra_keys = set(value) - set(MLResultIn.model_fields)
    if extra_keys:
        logger.warning("Dropping unknown ML result keys: %s", sorted(map(str, extra_keys)))
    payload = {key: item for key, item in value.items() if key in MLResultIn.model_fields}
    try:
        return MLResultIn.model_validate(payload)
    except ValidationError as exc:
        raise MLClientError(
            "ML result is missing required fields or contains invalid values"
        ) from exc


def validate_result_identity(result: MLResultIn, record: TelemetryIn) -> MLResultIn:
    if result.transformer_id != record.transformer_id or result.timestamp != record.timestamp:
        raise MLClientError("ML result identity and timestamp must match the current record")
    return result
