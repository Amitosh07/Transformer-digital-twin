"""Phase 6 extension point. Ingestion isolates hook failures with a savepoint."""

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.telemetry import Telemetry


def evaluate_alerts(session: Session, telemetry_row: Telemetry, analytics_row: Analytics) -> None:
    pass
