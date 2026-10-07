"""Pure alert predicates and separately orchestrated transactional lifecycle."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.core.config import Settings, get_settings
from app.models.analytics import Analytics
from app.models.telemetry import Telemetry
from app.repositories import alert_repo, transformer_repo
from app.repositories.telemetry_repo import as_input
from app.schemas.alert import AlertOut
from app.schemas.analytics import AnalyticsOut, MLResultIn
from app.schemas.telemetry import TelemetryIn

Severity = Literal["INFO", "WARNING", "CRITICAL"]
SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
PROTECTION_RULES: dict[str, tuple[str, Severity]] = {
    "OIL_TEMP_TRIP": ("oil_temp_trip", "CRITICAL"),
    "OIL_TEMP_ALARM": ("oil_temp_alarm", "WARNING"),
    "MOG_ALARM": ("magnetic_oil_gauge_alarm", "WARNING"),
}
PROXY_WORDING = "proxy risk (alarm/trip-based prediction)"
ACTIONS = {
    "OIL_TEMP_TRIP": "Urgently inspect the trip indication using site procedures.",
    "OIL_TEMP_ALARM": "Inspect the oil temperature alarm indication.",
    "MOG_ALARM": "Inspect the magnetic oil gauge alarm indication.",
    "ANOMALOUS_PATTERN": "Review the anomalous pattern and available sensor evidence.",
    "HIGH_OIL_TEMP": "Review the reported thermal reason and available sensor evidence.",
    "RAPID_TEMP_RISE": "Review the temperature trend reported by the ML adapter.",
    "OVERLOAD": "Review loading evidence and configured nameplate ratings.",
    "CURRENT_IMBALANCE": "Inspect the phase current measurements and reported imbalance.",
    "VOLTAGE_IMBALANCE": "Inspect the phase voltage measurements and reported imbalance.",
    "LOW_OIL_LEVEL": "Inspect the oil level indication using site procedures.",
    "LOW_HEALTH_INDEX": "Review the health components and plan an inspection.",
    "MAINTENANCE_URGENT": "Arrange urgent inspection of the reported indications.",
    "MAINTENANCE_PLAN": "Plan inspection of the reported indications.",
    "MAINTENANCE_WATCH": "Monitor the reported indications.",
}


@dataclass(frozen=True)
class AlertCandidate:
    alert_type: str
    severity: Severity
    trigger: str
    evidence: dict[str, Any]
    threshold_or_reason: str
    recommended_action: str


def alert_candidates(
    record: TelemetryIn, analytics: MLResultIn, settings: Settings
) -> list[AlertCandidate]:
    candidates: dict[str, AlertCandidate] = {}

    def add(
        kind: str,
        severity: Severity,
        trigger: str,
        evidence: dict[str, Any],
        reason: str,
        action: str | None = None,
    ) -> None:
        candidate = AlertCandidate(
            kind,
            severity,
            trigger,
            evidence,
            reason,
            action
            or ACTIONS.get(kind, "Review the reported reason and canonical sensor evidence."),
        )
        prior = candidates.get(kind)
        if prior is not None:
            winner = candidate if SEVERITY_RANK[severity] > SEVERITY_RANK[prior.severity] else prior
            candidate = replace(
                winner,
                evidence=prior.evidence | evidence,
                threshold_or_reason=prior.threshold_or_reason + "; " + reason,
            )
        candidates[kind] = candidate

    for kind, (field, severity) in PROTECTION_RULES.items():
        if getattr(record, field) == 1:
            add(kind, severity, field, {field: getattr(record, field)}, kind)
    if analytics.inference_status != "OK":
        return sorted(candidates.values(), key=lambda item: item.alert_type)
    if analytics.anomaly_flag is True:
        critical = (
            analytics.anomaly_score is not None
            and analytics.anomaly_score >= settings.alert_anomaly_critical
        )
        add(
            "ANOMALOUS_PATTERN",
            "CRITICAL" if critical else "WARNING",
            "anomaly_flag",
            {"anomaly_flag": analytics.anomaly_flag, "anomaly_score": analytics.anomaly_score},
            f"anomaly_flag=true; ALERT_ANOMALY_CRITICAL={settings.alert_anomaly_critical}",
        )
    priorities: dict[str, Severity] = {"URGENT": "CRITICAL", "PLAN": "WARNING", "WATCH": "INFO"}
    if analytics.maintenance_priority in priorities:
        add(
            "MAINTENANCE_" + analytics.maintenance_priority,
            priorities[analytics.maintenance_priority],
            "maintenance_priority",
            {
                "maintenance_priority": analytics.maintenance_priority,
                "maintenance_recommendation": analytics.maintenance_recommendation,
                "reason_codes": analytics.reason_codes,
            },
            analytics.maintenance_priority,
        )
    health = analytics.health_index
    if health is not None and health < settings.alert_health_warn:
        severity: Severity = "CRITICAL" if health < settings.alert_health_crit else "WARNING"
        threshold = (
            settings.alert_health_crit if severity == "CRITICAL" else settings.alert_health_warn
        )
        add(
            "LOW_HEALTH_INDEX",
            severity,
            "health_index",
            {"health_index": health},
            f"health_index < {threshold}",
        )
    risk = analytics.fault_risk
    if risk is not None and risk >= settings.alert_fault_risk_warn:
        severity = "CRITICAL" if risk >= settings.alert_fault_risk_crit else "WARNING"
        threshold = (
            settings.alert_fault_risk_crit
            if severity == "CRITICAL"
            else settings.alert_fault_risk_warn
        )
        add(
            "PROXY_FAULT_RISK",
            severity,
            "fault_risk",
            {
                "fault_risk": risk,
                "predicted_fault": analytics.predicted_fault,
                "prediction_confidence": analytics.prediction_confidence,
            },
            f"fault_risk >= {threshold}; {PROXY_WORDING}",
            "Review " + PROXY_WORDING + " and inspect the indications.",
        )
    for code in sorted(set(analytics.reason_codes or [])):
        if code in settings.alert_reason_severity and code not in PROTECTION_RULES:
            add(
                code,
                settings.alert_reason_severity[code],
                "reason_codes",
                {"reason_codes": analytics.reason_codes},
                code,
            )
    return sorted(candidates.values(), key=lambda item: item.alert_type)


def evaluate(session: Session, telemetry_row: Telemetry, analytics_row: Analytics) -> None:
    settings = get_settings()
    candidates = alert_candidates(
        as_input(telemetry_row), AnalyticsOut.model_validate(analytics_row), settings
    )
    active = {
        row.alert_type: row for row in alert_repo.active(session, telemetry_row.transformer_id)
    }
    triggered = {candidate.alert_type for candidate in candidates}
    for candidate in candidates:
        row = active.get(candidate.alert_type)
        if row is None:
            row = alert_repo.insert_active(
                session,
                {
                    "transformer_id": telemetry_row.transformer_id,
                    "telemetry_id": telemetry_row.id,
                    "analytics_id": analytics_row.id,
                    "timestamp": telemetry_row.timestamp,
                    "last_seen_at": telemetry_row.timestamp,
                    "status": "OPEN",
                    "clear_count": 0,
                    **candidate.__dict__,
                },
            )
        if telemetry_row.timestamp < row.last_seen_at:
            continue
        row.last_seen_at = telemetry_row.timestamp
        row.evidence = candidate.evidence
        row.trigger = candidate.trigger
        row.threshold_or_reason = candidate.threshold_or_reason
        row.recommended_action = candidate.recommended_action
        row.telemetry_id = telemetry_row.id
        row.analytics_id = analytics_row.id
        row.clear_count = 0
        if SEVERITY_RANK[candidate.severity] > SEVERITY_RANK[row.severity]:
            row.severity = candidate.severity
    for kind, row in sorted(active.items()):
        if kind in triggered or telemetry_row.timestamp < row.last_seen_at:
            continue
        if analytics_row.inference_status != "OK" and kind not in PROTECTION_RULES:
            continue
        row.clear_count += 1
        if row.clear_count >= settings.alert_auto_resolve_after:
            row.status = "RESOLVED"
            row.resolved_at = telemetry_row.timestamp
    session.flush()


def get_alert(session: Session, alert_id: int) -> AlertOut:
    row = alert_repo.get(session, alert_id)
    if row is None:
        raise HTTPException(404, "Alert not found")
    return AlertOut.model_validate(row)


def transition(
    session: Session, alert_id: int, action: Literal["acknowledge", "resolve"]
) -> AlertOut:
    row = alert_repo.get(session, alert_id)
    if row is None:
        raise HTTPException(404, "Alert not found")
    transformer_repo.lock_for_ingestion(session, row.transformer_id)
    row = alert_repo.get(session, alert_id, lock=True)
    if row is None:
        raise HTTPException(404, "Alert not found")
    if action == "acknowledge":
        if row.status == "RESOLVED":
            raise HTTPException(409, "Resolved alerts cannot be acknowledged")
        if row.status == "OPEN":
            row.status = "ACKNOWLEDGED"
            row.acknowledged_at = datetime.now(UTC)
    elif row.status != "RESOLVED":
        row.status = "RESOLVED"
        row.resolved_at = datetime.now(UTC)
    session.flush()
    result = AlertOut.model_validate(row)
    session.commit()
    return result
