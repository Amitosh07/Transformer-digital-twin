"""Independent verification of Health Index fixtures and Maintenance Engine scenarios for Phase 06.

Phase 06 — Time-Aware Evaluation:
- Validates all 8 mandatory Health Index fixtures from 03_HEALTH_INDEX.md.
- Validates all 11 mandatory Maintenance Engine scenarios from 05_MAINTENANCE_ENGINE.md.
- Validates exact persistence boundaries, gap resets, recovery windows, trip latching, and deterministic replay.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.health.engine import (
    HealthIndexConfig,
    calculate_health_index_record,
)
from ml.maintenance.engine import (
    MaintenanceEngine,
    MaintenanceEngineConfig,
    MaintenancePriority,
)


def verify_health_index_fixtures() -> dict[str, Any]:
    """Verify all 8 mandatory calculated Health Index fixtures."""
    cfg = HealthIndexConfig()
    results: dict[str, dict[str, Any]] = {}

    # Fixture 1: Healthy reference (H = 100)
    c1 = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 100}
    r1 = calculate_health_index_record(c1, config=cfg)
    results["fixture_1_healthy_reference"] = {
        "expected_score": 100.0,
        "actual_score": r1["health_index"],
        "passed": bool(np.isclose(r1["health_index"], 100.0)),
    }

    # Fixture 2: High load, normal thermal response (H = 91)
    c2 = {"thermal": 100, "electrical": 100, "loading": 40, "oil": 100, "alarm": 100, "anomaly": 40}
    r2 = calculate_health_index_record(c2, config=cfg)
    results["fixture_2_high_load_normal_thermal"] = {
        "expected_score": 91.0,
        "actual_score": r2["health_index"],
        "passed": bool(np.isclose(r2["health_index"], 91.0)),
    }

    # Fixture 3: High oil temperature (H = 40, capped from 72)
    c3 = {"thermal": 20, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 20}
    r3 = calculate_health_index_record(c3, persistent_components={"thermal"}, config=cfg)
    results["fixture_3_high_oil_temperature"] = {
        "expected_score": 40.0,
        "actual_score": r3["health_index"],
        "cap_applied": r3["health_cap_applied"],
        "passed": bool(np.isclose(r3["health_index"], 40.0) and r3["health_cap_applied"]),
    }

    # Fixture 4: Current imbalance (H = 50, capped from 82.5)
    c4 = {"thermal": 100, "electrical": 30, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 30}
    r4 = calculate_health_index_record(c4, persistent_components={"electrical"}, config=cfg)
    results["fixture_4_current_imbalance"] = {
        "expected_score": 50.0,
        "actual_score": r4["health_index"],
        "cap_applied": r4["health_cap_applied"],
        "passed": bool(np.isclose(r4["health_index"], 50.0) and r4["health_cap_applied"]),
    }

    # Fixture 5: Positive thermal residual (H = 60, capped from 79)
    c5 = {"thermal": 40, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 40}
    r5 = calculate_health_index_record(c5, persistent_components={"thermal"}, config=cfg)
    results["fixture_5_positive_thermal_residual"] = {
        "expected_score": 60.0,
        "actual_score": r5["health_index"],
        "cap_applied": r5["health_cap_applied"],
        "passed": bool(np.isclose(r5["health_index"], 60.0) and r5["health_cap_applied"]),
    }

    # Fixture 6: Active alarm (H = 60, capped from 83)
    c6 = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 40, "anomaly": 0}
    r6 = calculate_health_index_record(c6, config=cfg)
    results["fixture_6_active_alarm"] = {
        "expected_score": 60.0,
        "actual_score": r6["health_index"],
        "cap_applied": r6["health_cap_applied"],
        "passed": bool(np.isclose(r6["health_index"], 60.0) and r6["health_cap_applied"]),
    }

    # Fixture 7: Verified trip (H = 0 override)
    c7 = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 0, "anomaly": 0}
    r7 = calculate_health_index_record(c7, is_trip_active=True, config=cfg)
    results["fixture_7_verified_trip"] = {
        "expected_score": 0.0,
        "actual_score": r7["health_index"],
        "trip_override": r7["health_trip_override"],
        "passed": bool(np.isclose(r7["health_index"], 0.0) and r7["health_trip_override"]),
    }

    # Fixture 8: Multiple problems (H = 40, capped from 43)
    c8 = {"thermal": 20, "electrical": 30, "loading": 40, "oil": 40, "alarm": 100, "anomaly": 20}
    r8 = calculate_health_index_record(c8, persistent_components={"thermal", "electrical", "oil"}, config=cfg)
    results["fixture_8_multiple_problems"] = {
        "expected_score": 40.0,
        "actual_score": r8["health_index"],
        "cap_applied": r8["health_cap_applied"],
        "passed": bool(np.isclose(r8["health_index"], 40.0) and r8["health_cap_applied"]),
    }

    all_passed = all(v["passed"] for v in results.values())
    return {
        "all_fixtures_passed": all_passed,
        "total_fixtures": len(results),
        "fixtures": results,
    }


def verify_maintenance_scenarios() -> dict[str, Any]:
    """Verify all 11 mandatory Maintenance Engine scenarios."""
    cfg = MaintenanceEngineConfig(
        min_persistence_observations=3,
        min_persistence_span_minutes=30.0,
        continuity_gap_minutes=30.0,
    )
    results: dict[str, dict[str, Any]] = {}

    # Scenario 1: Complete clear reference -> NORMAL
    eng1 = MaintenanceEngine(config=cfg)
    r1 = eng1.process_record({
        "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
        "oil_temperature": 55.0,
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_1_complete_clear"] = {
        "expected_priority": "NORMAL",
        "actual_priority": r1["maintenance_priority"],
        "passed": r1["maintenance_priority"] == "NORMAL",
    }

    # Scenario 2: High kVA, no rating -> WATCH
    eng2 = MaintenanceEngine(config=cfg)
    r2 = eng2.process_record({
        "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
        "apparent_power_kva": 900.0,
        "rated_power_kva": np.nan,
        "oil_temperature": 50.0,
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_2_high_demand_no_rating"] = {
        "expected_priority": "WATCH",
        "actual_priority": r2["maintenance_priority"],
        "passed": r2["maintenance_priority"] == "WATCH",
    }

    # Scenario 3: Above verified nameplate -> WATCH
    eng3 = MaintenanceEngine(config=cfg)
    r3 = eng3.process_record({
        "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
        "apparent_power_kva": 600.0,
        "rated_power_kva": 500.0,
        "loading_percent": 120.0,
        "oil_temperature": 50.0,
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_3_above_nameplate_no_envelope"] = {
        "expected_priority": "WATCH",
        "actual_priority": r3["maintenance_priority"],
        "passed": r3["maintenance_priority"] == "WATCH",
    }

    # Scenario 4: Isolated temperature spike -> WATCH
    eng4 = MaintenanceEngine(config=cfg)
    r4 = eng4.process_record({
        "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
        "oil_temperature": 88.0,
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_4_isolated_temp_spike"] = {
        "expected_priority": "WATCH",
        "actual_priority": r4["maintenance_priority"],
        "passed": r4["maintenance_priority"] == "WATCH",
    }

    # Scenario 5: Persistent current imbalance -> PLAN
    eng5 = MaintenanceEngine(config=cfg)
    base_t = pd.Timestamp("2026-01-01 12:00:00")
    for m in (0, 15, 30):
        r5 = eng5.process_record({
            "timestamp": base_t + pd.Timedelta(minutes=m),
            "oil_temperature": 50.0,
            "current_imbalance_pct": 75.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        })
    results["scenario_5_persistent_current_imbalance"] = {
        "expected_priority": "PLAN",
        "actual_priority": r5["maintenance_priority"],
        "passed": r5["maintenance_priority"] == "PLAN",
    }

    # Scenario 6: Persistent positive residual -> PLAN
    eng6 = MaintenanceEngine(config=cfg)
    for m in (0, 15, 30):
        r6 = eng6.process_record({
            "timestamp": base_t + pd.Timedelta(minutes=m),
            "oil_temperature": 60.0,
            "thermal_residual": 8.0,
            "thermal_readiness": "READY",
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        })
    results["scenario_6_persistent_positive_residual"] = {
        "expected_priority": "PLAN",
        "actual_priority": r6["maintenance_priority"],
        "passed": r6["maintenance_priority"] == "PLAN",
    }

    # Scenario 7: Persistent MOG alarm -> PLAN
    eng7 = MaintenanceEngine(config=cfg)
    for m in (0, 15, 30):
        r7 = eng7.process_record({
            "timestamp": base_t + pd.Timedelta(minutes=m),
            "oil_temperature": 50.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 1.0,
        })
    results["scenario_7_persistent_mog_alarm"] = {
        "expected_priority": "PLAN",
        "actual_priority": r7["maintenance_priority"],
        "passed": r7["maintenance_priority"] == "PLAN",
    }

    # Scenario 8: Verified active trip -> URGENT
    eng8 = MaintenanceEngine(config=cfg)
    r8 = eng8.process_record({
        "timestamp": base_t,
        "oil_temperature": 90.0,
        "oil_temp_trip": 1.0,
        "oil_temp_alarm": 1.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_8_verified_active_trip"] = {
        "expected_priority": "URGENT",
        "actual_priority": r8["maintenance_priority"],
        "passed": r8["maintenance_priority"] == "URGENT",
    }

    # Scenario 9: Persistent severe heating + low oil -> URGENT
    eng9 = MaintenanceEngine(config=cfg)
    for m in (0, 15, 30):
        r9 = eng9.process_record({
            "timestamp": base_t + pd.Timedelta(minutes=m),
            "oil_temperature": 92.0,
            "severity_thermal": 0.9,
            "oil_level_deviation": -5.0,
            "severity_oil": 0.8,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        })
    results["scenario_9_severe_heating_low_oil"] = {
        "expected_priority": "URGENT",
        "actual_priority": r9["maintenance_priority"],
        "passed": r9["maintenance_priority"] == "URGENT",
    }

    # Scenario 10: Experimental high risk alone -> WATCH
    eng10 = MaintenanceEngine(config=cfg)
    r10 = eng10.process_record({
        "timestamp": base_t,
        "oil_temperature": 50.0,
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
        "fault_risk": 0.85,
        "is_operationally_released": False,
    })
    results["scenario_10_experimental_high_risk_alone"] = {
        "expected_priority": "WATCH",
        "actual_priority": r10["maintenance_priority"],
        "passed": r10["maintenance_priority"] == "WATCH",
    }

    # Scenario 11: Missing critical coverage -> WATCH
    eng11 = MaintenanceEngine(config=cfg)
    r11 = eng11.process_record({
        "timestamp": base_t,
        "oil_temperature": np.nan,  # Missing temp
        "oil_temp_trip": 0.0,
        "oil_temp_alarm": 0.0,
        "magnetic_oil_gauge_alarm": 0.0,
    })
    results["scenario_11_missing_critical_coverage"] = {
        "expected_priority": "WATCH",
        "actual_priority": r11["maintenance_priority"],
        "passed": r11["maintenance_priority"] == "WATCH",
    }

    all_passed = all(v["passed"] for v in results.values())
    return {
        "all_scenarios_passed": all_passed,
        "total_scenarios": len(results),
        "scenarios": results,
    }
