import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "changes",
    [
        {"mqtt_queue_max": 0},
        {"mqtt_qos": 3},
        {"mqtt_qos": -1},
        {"mqtt_client_id": ""},
        {"mqtt_reconnect_min_s": 0},
        {"mqtt_reconnect_max_s": 0},
        {"mqtt_reconnect_min_s": 10, "mqtt_reconnect_max_s": 2},
        {"mqtt_topic": "a/+/+"},
        {"mqtt_topic": "a/#/b"},
        {"mqtt_topic": "a/b+"},
    ],
)
def test_invalid_mqtt_configuration(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


def test_defaults_and_empty_credentials() -> None:
    settings = Settings(_env_file=None, mqtt_username="", mqtt_password="")
    assert settings.mqtt_enabled is False
    assert settings.mqtt_topic == "transformer/+/telemetry"
    assert settings.mqtt_username is settings.mqtt_password is None
    assert settings.mqtt_port == 1883
    assert settings.mqtt_queue_max == 10000
