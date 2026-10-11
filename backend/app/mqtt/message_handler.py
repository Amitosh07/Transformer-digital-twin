"""Pure canonical message validation; rejection objects never retain payloads."""

from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.telemetry import TelemetryIn


class MessageRejected(ValueError):
    def __init__(self, reason: str, field: str | None = None) -> None:
        self.reason = reason
        self.field = field
        super().__init__(reason)


def _topic_identity(topic: str, pattern: str) -> str | None:
    actual, expected = topic.split("/"), pattern.split("/")
    identity = None
    for index, segment in enumerate(expected):
        if segment == "#":
            return identity
        if index >= len(actual):
            raise MessageRejected("TOPIC_MISMATCH")
        if segment == "+":
            identity = actual[index]
        elif segment != actual[index]:
            raise MessageRejected("TOPIC_MISMATCH")
    if len(actual) != len(expected):
        raise MessageRejected("TOPIC_MISMATCH")
    return identity


def parse_message(topic: str, payload: bytes) -> list[TelemetryIn]:
    settings = get_settings()
    if not payload.strip():
        raise MessageRejected("EMPTY_PAYLOAD")
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise MessageRejected("INVALID_UTF8") from None
    try:
        from ml.pipeline.identity import parse_record_json
        value: Any = parse_record_json(decoded)
    except (ValueError, RecursionError):
        raise MessageRejected("INVALID_JSON") from None
    if isinstance(value, dict):
        rows = [value]
    elif isinstance(value, list):
        rows = value
    else:
        raise MessageRejected("INVALID_TOP_LEVEL")
    if not rows:
        raise MessageRejected("EMPTY_RECORDS")
    if len(rows) > settings.max_batch_size:
        raise MessageRejected("BATCH_TOO_LARGE", "records")
    identity = _topic_identity(topic, settings.mqtt_topic)
    records = []
    for row in rows:
        if not isinstance(row, dict):
            raise MessageRejected("INVALID_RECORD", "records")
        row = dict(row)
        if "transformer_id" not in row and identity is not None:
            row["transformer_id"] = identity
        elif identity is not None and row.get("transformer_id") != identity:
            raise MessageRejected("TOPIC_ID_MISMATCH", "transformer_id")
        # MQTT is transport; preserve absent semantic source fields as null.
        try:
            records.append(TelemetryIn.model_validate(row))
        except ValidationError as exc:
            error = exc.errors(include_input=False, include_context=False)[0]
            location = error["loc"]
            # Unknown keys can themselves contain secrets. Only expose known field names.
            field = str(location[0]) if location else None
            if field not in TelemetryIn.model_fields:
                field = None
            reason = "VALIDATION_ERROR"
            if not location and "excluded" in error["msg"].lower():
                reason = "EXCLUDED_FIELD"
            raise MessageRejected(reason, field) from None
    return records
