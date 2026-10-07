from unittest.mock import Mock

from app.core.config import get_settings
from app.schemas.mqtt import MqttStatus
from app.services.mqtt_status_service import initial_status, mqtt_status


def test_initial_status_and_provider() -> None:
    expected = initial_status(get_settings())
    assert MqttStatus.model_validate(expected).enabled is False
    assert mqtt_status(None) == expected
    provider = Mock()
    provider.status.return_value = {**expected, "ingested_count": 3}
    assert mqtt_status(provider)["ingested_count"] == 3
