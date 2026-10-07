from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Alert, Analytics, MaintenanceRecord, Telemetry, Transformer
from app.schemas.alert import AlertOut
from app.schemas.analytics import AnalyticsOut
from app.schemas.maintenance import MaintenanceOut
from app.schemas.state import LatestStateOut
from app.schemas.telemetry import TelemetryOut
from app.schemas.transformer import TransformerOut

NOW = datetime(2026, 10, 6, tzinfo=UTC)


@pytest.mark.postgres
def test_every_out_model_converts_postgres_orm_and_latest_state(db: Session) -> None:
    transformer = Transformer(id="TX-schema", name="Schema test")
    db.add(transformer)
    db.flush()
    telemetry = Telemetry(
        transformer_id=transformer.id,
        timestamp=NOW,
        oil_temperature=0,
        source_name="simulator",
        scenario_id="scenario-1",
        schema_version="1.0.0",
    )
    db.add(telemetry)
    db.flush()
    analytics = Analytics(
        telemetry_id=telemetry.id,
        transformer_id=transformer.id,
        timestamp=NOW,
        inference_status="INSUFFICIENT_DATA",
        missing_features=["current_l1"],
        schema_version="1.0.0",
        feature_version="1.0.0",
        model_version="stub",
    )
    db.add(analytics)
    db.flush()
    alert = Alert(
        transformer_id=transformer.id,
        analytics_id=analytics.id,
        telemetry_id=telemetry.id,
        timestamp=NOW,
        severity="INFO",
        alert_type="DATA_QUALITY",
        trigger="missing_features",
        evidence={"missing_features": ["current_l1"]},
        threshold_or_reason="Missing current",
        recommended_action="Check source",
    )
    maintenance = MaintenanceRecord(
        transformer_id=transformer.id,
        analytics_id=analytics.id,
        timestamp=NOW,
        priority="WATCH",
        recommendation="Check source",
        reason_codes=[],
    )
    db.add_all([alert, maintenance])
    db.flush()
    db.expire_all()
    transformer_out = TransformerOut.model_validate(transformer)
    telemetry_out = TelemetryOut.model_validate(telemetry)
    analytics_out = AnalyticsOut.model_validate(analytics)
    alert_out = AlertOut.model_validate(alert)
    maintenance_out = MaintenanceOut.model_validate(maintenance)
    assert telemetry_out.source_name == "simulator"
    assert telemetry_out.current_l1 is None
    assert analytics_out.health_components is None
    assert transformer_out.rated_power_kva is None
    assert alert_out.status == "OPEN"
    assert alert_out.acknowledged_at is None
    assert maintenance_out.priority == "WATCH"
    for record in [transformer_out, telemetry_out, analytics_out, alert_out, maintenance_out]:
        assert record.model_config["from_attributes"] is True
        assert record.model_config["extra"] == "forbid"
        record.model_dump_json()
    state = LatestStateOut(
        transformer=transformer,
        telemetry=telemetry,
        analytics=analytics,
        open_alerts_count=1,
        demo_mode=True,
        schema_version="1.0.0",
        feature_version="1.0.0",
        model_version="stub",
    )
    dumped = state.model_dump(mode="json")
    assert dumped["telemetry"]["timestamp"] == "2026-10-06T00:00:00Z"
    assert dumped["analytics"]["health_index"] is None
    assert dumped["transformer"]["rated_power_kva"] is None
    assert dumped["data_source"] == {"source_name": None, "scenario_id": None}
    assert set(dumped) == {
        "transformer",
        "telemetry",
        "analytics",
        "open_alerts_count",
        "demo_mode",
        "data_source",
        "schema_version",
        "feature_version",
        "model_version",
    }
    empty_state = LatestStateOut(
        transformer=transformer, open_alerts_count=0, demo_mode=False, schema_version="1.0.0"
    )
    assert empty_state.telemetry is None
    assert empty_state.analytics is None
    assert empty_state.feature_version is None
    with pytest.raises(ValidationError):
        LatestStateOut(
            transformer=transformer, open_alerts_count=-1, demo_mode=False, schema_version="1.0.0"
        )
    # Enum and timestamp validation also applies to ORM attributes.
    alert.severity = "INVALID"
    with pytest.raises(ValidationError):
        AlertOut.model_validate(alert)
    maintenance.status = "INVALID"
    with pytest.raises(ValidationError):
        MaintenanceOut.model_validate(maintenance)
