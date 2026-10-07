import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.config import get_settings
from app.mqtt.message_handler import MessageRejected, parse_message

TOPIC = "transformer/TX-parse/telemetry"
BASE = {"timestamp": "2026-10-07T14:30:00+05:30"}


def encode(value: Any) -> bytes:
    return json.dumps(value).encode()


def test_single_and_array_preserve_nulls_metadata_and_utc() -> None:
    record = parse_message(
        TOPIC, encode({**BASE, "oil_temp_alarm": True, "scenario_id": "scenario", "current_l1": 0})
    )[0]
    assert record.transformer_id == "TX-parse"
    assert record.timestamp == datetime(2026, 10, 7, 9, tzinfo=UTC)
    assert record.source_name == "mqtt"
    assert record.scenario_id == "scenario"
    assert record.oil_temp_alarm == 1
    assert record.current_l1 == 0
    assert record.oil_temperature is None
    records = parse_message(TOPIC, encode([BASE, {**BASE, "source_name": "simulator"}]))
    assert len(records) == 2
    assert records[1].source_name == "simulator"


@pytest.mark.parametrize("key", ["V" + "L12", "v" + "l23", "V" + "L31", "V" + "L_12"])
def test_excluded_fields(key: str) -> None:
    with pytest.raises(MessageRejected, match="EXCLUDED_FIELD"):
        parse_message(TOPIC, encode({**BASE, key: 1}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("secret-field", "secret-value"),
        ("timestamp", "2026-10-07T09:00:00"),
        ("oil_temperature", float("nan")),
        ("oil_temperature", float("inf")),
        ("oil_level", float("-inf")),
        ("oil_temp_alarm", 2),
        ("power_factor_l1", 1.5),
        ("oil_temperature", "secret-value"),
    ],
)
def test_validation_never_exposes_payload(field: str, value: Any) -> None:
    with pytest.raises(MessageRejected) as caught:
        parse_message(TOPIC, encode({**BASE, field: value}))
    assert caught.value.reason == "VALIDATION_ERROR"
    assert "secret" not in str(caught.value)
    assert "secret" not in repr(caught.value)
    assert caught.value.field == (None if field == "secret-field" else field)


@pytest.mark.parametrize(
    "payload,reason",
    [
        (b"", "EMPTY_PAYLOAD"),
        (b"   ", "EMPTY_PAYLOAD"),
        (b"\xff", "INVALID_UTF8"),
        (b"secret-invalid-json", "INVALID_JSON"),
        (b"null", "INVALID_TOP_LEVEL"),
        (b"1", "INVALID_TOP_LEVEL"),
        (b'"secret"', "INVALID_TOP_LEVEL"),
        (b"[]", "EMPTY_RECORDS"),
        (b"[1]", "INVALID_RECORD"),
    ],
)
def test_bad_envelopes(payload: bytes, reason: str) -> None:
    with pytest.raises(MessageRejected) as caught:
        parse_message(TOPIC, payload)
    assert str(caught.value) == reason


def test_topic_payload_mismatch() -> None:
    with pytest.raises(MessageRejected, match="TOPIC_ID_MISMATCH"):
        parse_message(TOPIC, encode({**BASE, "transformer_id": "different"}))


def test_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_BATCH_SIZE", "2")
    get_settings.cache_clear()
    with pytest.raises(MessageRejected, match="BATCH_TOO_LARGE"):
        parse_message(TOPIC, encode([BASE] * 3))


def test_custom_topic_and_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_TOPIC", "site/telemetry/+")
    monkeypatch.setenv("MQTT_SOURCE_NAME", "mqtt-simulator")
    get_settings.cache_clear()
    record = parse_message("site/telemetry/TX-custom", encode(BASE))[0]
    assert record.transformer_id == "TX-custom"
    assert record.source_name == "mqtt-simulator"
    with pytest.raises(MessageRejected, match="TOPIC_MISMATCH"):
        parse_message("other/telemetry/TX-custom", encode(BASE))


def test_fixed_and_multilevel_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_TOPIC", "telemetry/#")
    get_settings.cache_clear()
    records = parse_message("telemetry/site", encode({**BASE, "transformer_id": "TX-fixed"}))
    assert records[0].transformer_id == "TX-fixed"
    with pytest.raises(MessageRejected, match="VALIDATION_ERROR"):
        parse_message("telemetry/site", encode(BASE))


def test_array_is_rejected_as_a_whole() -> None:
    with pytest.raises(MessageRejected):
        parse_message(TOPIC, encode([BASE, {**BASE, "oil_temp_alarm": 2}]))
