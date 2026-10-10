from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


@pytest.fixture
def ml_settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def transformer() -> TransformerOut:
    return TransformerOut(
        id="TX-001",
        name="Test transformer",
        created_at=datetime(2026, 10, 6, tzinfo=UTC),
        updated_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


@pytest.fixture
def record() -> TelemetryIn:
    return TelemetryIn(
        transformer_id="TX-001",
        timestamp=datetime(2026, 10, 6, 9, tzinfo=UTC),
        oil_temperature=42,
        oil_level=8,
    )


@pytest.fixture
def history(record: TelemetryIn) -> list[TelemetryIn]:
    return [
        record.model_copy(update={"timestamp": record.timestamp - timedelta(minutes=offset)})
        for offset in [2, 1]
    ]


@pytest.fixture
def valid_result(record: TelemetryIn) -> MLResultIn:
    return MLResultIn(
        transformer_id=record.transformer_id,
        timestamp=record.timestamp,
        inference_status="OK",
        health_index=90,
        schema_version="1.0.0",
        feature_version="1.0.0",
        model_version="test-1.0.0",
    )
