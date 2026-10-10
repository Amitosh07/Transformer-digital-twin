from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.alert_service import PROTECTION_RULES, alert_candidates
from app.services.maintenance_service import maintenance_candidate
from tests.alerts.conftest import record, result


def candidates(**outputs: Any) -> dict[str, Any]:
    telemetry = record("TX-rules")
    return {
        item.alert_type: item
        for item in alert_candidates(telemetry, result(telemetry, **outputs), get_settings())
    }


@pytest.mark.parametrize(
    "kind,field,severity",
    [
        ("OIL_TEMP_TRIP", "oil_temp_trip", "CRITICAL"),
        ("OIL_TEMP_ALARM", "oil_temp_alarm", "WARNING"),
        ("MOG_ALARM", "magnetic_oil_gauge_alarm", "WARNING"),
    ],
)
@pytest.mark.parametrize("status", ["OK", "INSUFFICIENT_DATA"])
def test_protection_rule(kind: str, field: str, severity: str, status: str) -> None:
    telemetry = record("TX-rules", **{field: 1})
    rows = alert_candidates(telemetry, result(telemetry, inference_status=status), get_settings())
    assert [(row.alert_type, row.severity) for row in rows] == [(kind, severity)]
    assert rows[0].evidence == {field: 1}
    assert rows[0].recommended_action


@pytest.mark.parametrize("value", [0, None])
def test_untriggered_protection_and_unverified_measurements(value: int | None) -> None:
    telemetry = record(
        "TX-rules",
        oil_temp_alarm=value,
        oil_temp_trip=value,
        magnetic_oil_gauge_alarm=value,
        oil_temperature=-1e30,
        winding_temperature=1e30,
        ambient_temperature=-1e30,
        oil_level=1e30,
    )
    assert alert_candidates(telemetry, result(telemetry), get_settings()) == []


@pytest.mark.parametrize(
    "score,severity", [(None, "WARNING"), (0.8999, "WARNING"), (0.9, "CRITICAL"), (1, "CRITICAL")]
)
def test_anomaly_boundary(score: float | None, severity: str) -> None:
    row = candidates(anomaly_flag=True, anomaly_score=score)["ANOMALOUS_PATTERN"]
    assert row.severity == severity
    assert row.evidence == {"anomaly_flag": True, "anomaly_score": score}


@pytest.mark.parametrize("flag", [False, None])
def test_anomaly_requires_flag(flag: bool | None) -> None:
    assert not candidates(anomaly_flag=flag, anomaly_score=1)


@pytest.mark.parametrize(
    "health,severity",
    [
        (None, None),
        (60, None),
        (59.999, "WARNING"),
        (40, "WARNING"),
        (39.999, "CRITICAL"),
        (0, "CRITICAL"),
        (100, None),
    ],
)
def test_health_boundaries(health: float | None, severity: str | None) -> None:
    rows = candidates(health_index=health)
    assert list(rows) == (["LOW_HEALTH_INDEX"] if severity else [])
    if severity:
        assert rows["LOW_HEALTH_INDEX"].severity == severity
        assert rows["LOW_HEALTH_INDEX"].evidence == {"health_index": health}


@pytest.mark.parametrize(
    "risk,severity",
    [
        (None, None),
        (0.4999, None),
        (0.5, "WARNING"),
        (0.7999, "WARNING"),
        (0.8, "CRITICAL"),
        (1, "CRITICAL"),
    ],
)
def test_proxy_risk_boundaries(risk: float | None, severity: str | None) -> None:
    rows = candidates(fault_risk=risk)
    assert list(rows) == (["PROXY_FAULT_RISK"] if severity else [])
    if severity:
        row = rows["PROXY_FAULT_RISK"]
        assert row.severity == severity
        assert row.evidence == {
            "fault_risk": risk,
            "predicted_fault": None,
            "prediction_confidence": None,
        }
        assert "proxy risk (alarm/trip-based prediction)" in row.threshold_or_reason
        assert "proxy risk (alarm/trip-based prediction)" in row.recommended_action


@pytest.mark.parametrize(
    "priority,severity",
    [
        (None, None),
        ("NORMAL", None),
        ("WATCH", "INFO"),
        ("PLAN", "WARNING"),
        ("URGENT", "CRITICAL"),
    ],
)
def test_priority_rule(priority: str | None, severity: str | None) -> None:
    rows = candidates(maintenance_priority=priority)
    assert len(rows) == (1 if severity else 0)
    if severity:
        row = rows["MAINTENANCE_" + priority]
        assert row.severity == severity
        assert row.evidence["maintenance_recommendation"] is None
        assert row.evidence["reason_codes"] is None


@pytest.mark.parametrize(
    "code",
    [
        "HIGH_OIL_TEMP",
        "RAPID_TEMP_RISE",
        "OVERLOAD",
        "CURRENT_IMBALANCE",
        "VOLTAGE_IMBALANCE",
        "LOW_OIL_LEVEL",
        "ANOMALOUS_PATTERN",
    ],
)
def test_reason_mapping(code: str) -> None:
    rows = candidates(reason_codes=[code, code])
    assert list(rows) == [code]
    assert rows[code].severity == "WARNING"
    assert rows[code].evidence == {"reason_codes": [code, code]}


def test_reason_overlaps_merge_and_protection_codes_are_skipped() -> None:
    telemetry = record("TX-rules", oil_temp_alarm=1, oil_temp_trip=1, magnetic_oil_gauge_alarm=1)
    settings = Settings(
        _env_file=None,
        alert_reason_severity={
            **get_settings().alert_reason_severity,
            **dict.fromkeys(PROTECTION_RULES, "CRITICAL"),
        },
    )
    rows = alert_candidates(
        telemetry,
        result(
            telemetry,
            anomaly_flag=True,
            anomaly_score=0.95,
            reason_codes=["OIL_TEMP_ALARM", "OIL_TEMP_TRIP", "MOG_ALARM", "ANOMALOUS_PATTERN"],
        ),
        settings,
    )
    assert len(rows) == 4
    assert [row.alert_type for row in rows] == sorted(row.alert_type for row in rows)
    anomaly = next(row for row in rows if row.alert_type == "ANOMALOUS_PATTERN")
    assert anomaly.severity == "CRITICAL"
    assert anomaly.evidence["anomaly_score"] == 0.95
    assert anomaly.evidence["reason_codes"]
    assert next(row for row in rows if row.alert_type == "OIL_TEMP_ALARM").severity == "WARNING"


def test_all_ml_rules_skipped_on_insufficient() -> None:
    assert not candidates(
        inference_status="INSUFFICIENT_DATA",
        anomaly_flag=True,
        anomaly_score=1,
        health_index=0,
        fault_risk=1,
        maintenance_priority="URGENT",
        reason_codes=["HIGH_OIL_TEMP"],
    )


def test_configurable_thresholds_and_reason_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALERT_REASON_SEVERITY", '{"OVERLOAD":"CRITICAL"}')
    settings = Settings(
        _env_file=None,
        alert_health_warn=80,
        alert_health_crit=70,
        alert_anomaly_critical=0.6,
        alert_fault_risk_warn=0.2,
        alert_fault_risk_crit=0.3,
    )
    telemetry = record("TX-rules")
    rows = {
        row.alert_type: row
        for row in alert_candidates(
            telemetry,
            result(
                telemetry,
                health_index=65,
                anomaly_flag=True,
                anomaly_score=0.6,
                fault_risk=0.3,
                reason_codes=["OVERLOAD"],
            ),
            settings,
        )
    }
    assert set(rows) == {"LOW_HEALTH_INDEX", "ANOMALOUS_PATTERN", "PROXY_FAULT_RISK", "OVERLOAD"}
    assert all(row.severity == "CRITICAL" for row in rows.values())


@pytest.mark.parametrize(
    "values",
    [
        {"alert_health_crit": 70},
        {"alert_health_warn": -1},
        {"alert_fault_risk_crit": 0.1},
        {"alert_anomaly_critical": 1.1},
        {"alert_auto_resolve_after": 0},
        {"alert_health_warn": float("nan")},
        {"alert_fault_risk_warn": float("inf")},
        {"alert_reason_severity": {"OVERLOAD": "bad"}},
    ],
)
def test_invalid_config(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "priority,eligible",
    [(None, False), ("NORMAL", False), ("WATCH", False), ("PLAN", True), ("URGENT", True)],
)
@pytest.mark.parametrize("status", ["OK", "INSUFFICIENT_DATA"])
def test_maintenance_eligibility(priority: str | None, eligible: bool, status: str) -> None:
    telemetry = record("TX-rules")
    row = maintenance_candidate(
        result(
            telemetry,
            maintenance_priority=priority,
            inference_status=status,
            reason_codes=["OVERLOAD", "HIGH_OIL_TEMP", "OVERLOAD"],
        )
    )
    assert (row is not None) == (eligible and status == "OK")
    if row:
        assert row.reason_codes == ["HIGH_OIL_TEMP", "OVERLOAD"]
        assert row.recommendation
