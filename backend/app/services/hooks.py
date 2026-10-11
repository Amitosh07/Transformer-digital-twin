"""Alert and maintenance writes share the ingestion SQL transaction."""

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.telemetry import Telemetry
from app.services import alert_service, maintenance_service


def evaluate_alerts(session: Session, telemetry_row: Telemetry, analytics_row: Analytics | None) -> None:
    alert_service.evaluate(session, telemetry_row, analytics_row)
    if analytics_row is not None:
        maintenance_service.evaluate(session, analytics_row)
