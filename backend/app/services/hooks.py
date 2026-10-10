"""Alert and maintenance writes share the ingestion savepoint and session."""

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.telemetry import Telemetry
from app.services import alert_service, maintenance_service


def evaluate_alerts(session: Session, telemetry_row: Telemetry, analytics_row: Analytics) -> None:
    alert_service.evaluate(session, telemetry_row, analytics_row)
    maintenance_service.evaluate(session, analytics_row)
