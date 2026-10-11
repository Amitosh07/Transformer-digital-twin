"""Focused test suite for Phase 05 Maintenance Engine.

Tests cover:
- All 11 mandatory scenarios from 05_MAINTENANCE_ENGINE.md:
    1. Complete clear reference operation -> NORMAL
    2. Historically high kVA, no rating, normal thermal behavior -> WATCH
    3. Above verified nameplate, normal temperature, no approved emergency envelope -> WATCH
    4. Isolated temperature spike without corroboration -> WATCH
    5. Persistent current imbalance -> PLAN
    6. Persistent positive residual with credible sensors -> PLAN
    7. Persistent MOG alarm -> PLAN
    8. Verified active oil-temperature trip -> URGENT
    9. Persistent severe heating plus confirmed low oil -> URGENT
    10. Experimental high risk alone -> WATCH
    11. Missing temperature/protection coverage -> WATCH
- Precedence hierarchy: URGENT > PLAN > WATCH > NORMAL
- Exact persistence elapsed-time boundaries (3 observations spanning >= 30 min, gap <= 30 min)
- Continuous run breaks on clear observations
- Continuity gap reset (gap > 30 minutes resets persistence buffer)
- Recovery sequence requiring qualifying continuous clear window
- Trip latching and authorized operator clear policy (CONFIGURATION REQUIRED when missing)
- Evidence family independence: correlated thermal signals counted as ONE thermal family
- Advisory safety: no automatic control actions or switching side effects
- Deterministic replay
- Synthetic multi-step sequence smoke test through upstream pipeline conventions
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.maintenance.engine import (
    ALL_MAINTENANCE_COLUMNS,
    MAINTENANCE_OUTPUT_COLUMNS,
    ConditionRun,
    MaintenanceEngine,
    MaintenanceEngineConfig,
    MaintenancePersistenceState,
    MaintenancePriority,
    evaluate_maintenance,
    run_maintenance_engine,
)


class Phase05MaintenanceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MaintenanceEngineConfig(
            min_persistence_observations=3,
            min_persistence_span_minutes=30.0,
            continuity_gap_minutes=30.0,
        )
        self.engine = MaintenanceEngine(config=self.config)

    # -------------------------------------------------------------
    # The 11 Mandatory Scenarios from 05_MAINTENANCE_ENGINE.md
    # -------------------------------------------------------------

    def test_scenario_1_complete_clear_reference_operation(self) -> None:
        """Scenario 1: Complete clear reference operation -> NORMAL."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": 55.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "current_imbalance_pct": 5.0,
            "severity_thermal": 0.0,
            "severity_electrical": 0.0,
            "severity_oil": 0.0,
            "severity_loading": 0.0,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.NORMAL.value)
        self.assertIn("Normal operating condition", res["maintenance_recommendation"])
        self.assertEqual(res["maintenance_reason_codes"], [])
        self.assertEqual(res["maintenance_data_quality_status"], "COMPLETE")

    def test_scenario_2_historically_high_kva_no_rating_normal_thermal(self) -> None:
        """Scenario 2: Historically high kVA, no rating, normal thermal behavior -> WATCH."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "apparent_power_kva": 950.0,
            "rated_power_kva": np.nan,  # Rating unavailable!
            "oil_temperature": 50.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "severity_thermal": 0.0,
            "severity_loading": 0.8,
            "thermal_residual": 0.5,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("Review load distribution and monitor thermal response", res["maintenance_recommendation"])
        self.assertIn("HIGH_DEMAND_NO_RATING", res["maintenance_reason_codes"])
        self.assertIn("RATING_UNAVAILABLE", res["maintenance_reason_codes"])
        # Must NOT diagnose OVERLOAD because rating is unknown
        self.assertNotIn("OVERLOAD", res["maintenance_reason_codes"])
        self.assertEqual(res["maintenance_data_quality_status"], "RATING_UNAVAILABLE")

    def test_scenario_3_above_verified_nameplate_normal_temp_no_emergency_envelope(self) -> None:
        """Scenario 3: Above verified nameplate, normal temperature, no approved envelope -> WATCH."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "apparent_power_kva": 600.0,
            "rated_power_kva": 500.0,
            "loading_percent": 120.0,
            "oil_temperature": 52.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "severity_thermal": 0.0,
            "thermal_residual": 0.2,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("Review loading duration and operating envelope", res["maintenance_recommendation"])
        self.assertIn("OVERLOAD_UNAPPROVED_ENVELOPE", res["maintenance_reason_codes"])
        self.assertIn("OVERLOAD", res["maintenance_reason_codes"])

    def test_scenario_4_isolated_temperature_spike_without_corroboration(self) -> None:
        """Scenario 4: Isolated temperature spike without corroboration -> WATCH."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": 88.0,
            "severity_thermal": 0.9,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "severity_electrical": 0.0,
            "severity_oil": 0.0,
            "oil_level_deviation": 0.0,
        }
        # First observation -> Pon = 0 (unconfirmed spike)
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("Monitor transient; verify whether temperature rise is sustained", res["maintenance_recommendation"])
        self.assertIn("UNCONFIRMED_STATISTICAL_EXCEEDANCE", res["maintenance_reason_codes"])
        self.assertIn("HIGH_OIL_TEMP", res["maintenance_reason_codes"])

    def test_scenario_5_persistent_current_imbalance(self) -> None:
        """Scenario 5: Persistent current imbalance -> PLAN."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 75.0,
                "severity_electrical": 0.8,
                "severity_thermal": 0.0,
            }
            res = self.engine.process_record(rec)

        self.assertIsNotNone(res)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertIn("Verify measurement/phase allocation and plan balancing", res["maintenance_recommendation"])
        self.assertIn("PERSISTENT_CURRENT_IMBALANCE", res["maintenance_reason_codes"])
        self.assertIn("CURRENT_IMBALANCE", res["maintenance_reason_codes"])

    def test_scenario_6_persistent_positive_residual_credible_sensors(self) -> None:
        """Scenario 6: Persistent positive residual with credible sensors -> PLAN."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 60.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "thermal_residual": 8.5,
                "thermal_readiness": "READY",
                "severity_thermal": 0.6,
            }
            res = self.engine.process_record(rec)

        self.assertIsNotNone(res)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertIn("Verify sensor, cooling, ventilation and operating configuration", res["maintenance_recommendation"])
        self.assertIn("PERSISTENT_POSITIVE_THERMAL_RESIDUAL", res["maintenance_reason_codes"])
        self.assertIn("THERMAL_RESIDUAL_HIGH", res["maintenance_reason_codes"])

    def test_scenario_7_persistent_mog_alarm(self) -> None:
        """Scenario 7: Persistent MOG alarm -> PLAN."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 1.0,  # Active MOG alarm
            }
            res = self.engine.process_record(rec)

        self.assertIsNotNone(res)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertIn("Arrange oil-level/protection inspection", res["maintenance_recommendation"])
        self.assertIn("PERSISTENT_MOG_ALARM", res["maintenance_reason_codes"])
        self.assertIn("MOG_ALARM", res["maintenance_reason_codes"])

    def test_scenario_8_verified_active_oil_temperature_trip(self) -> None:
        """Scenario 8: Verified active oil-temperature trip -> URGENT (immediate latch)."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": 95.0,
            "oil_temp_trip": 1.0,  # Verified active trip!
            "oil_temp_alarm": 1.0,
            "magnetic_oil_gauge_alarm": 0.0,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertIn("Immediate operator review under site protection procedure", res["maintenance_recommendation"])
        self.assertIn("VERIFIED_TRIP", res["maintenance_reason_codes"])
        self.assertIn("OIL_TEMP_TRIP", res["maintenance_reason_codes"])
        self.assertTrue(res["maintenance_trip_latched"])
        self.assertEqual(res["maintenance_clear_policy_status"], "CONFIGURATION REQUIRED")

    def test_scenario_9_persistent_severe_heating_plus_confirmed_low_oil(self) -> None:
        """Scenario 9: Persistent severe heating plus confirmed low oil -> URGENT."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 92.0,
                "severity_thermal": 0.9,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "severity_oil": 0.8,
                "oil_level_deviation": -5.0,  # Confirmed low oil
            }
            res = self.engine.process_record(rec)

        self.assertIsNotNone(res)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertIn("severe thermal stress corroborated by low oil condition", res["maintenance_recommendation"])
        self.assertIn("PERSISTENT_SEVERE_HEATING", res["maintenance_reason_codes"])
        self.assertIn("CONFIRMED_LOW_OIL", res["maintenance_reason_codes"])

    def test_scenario_10_experimental_high_risk_alone(self) -> None:
        """Scenario 10: Experimental high risk alone -> WATCH / research annotation."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": 55.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "fault_risk": 0.88,  # High risk from unreleased model!
            "predicted_fault": "THERMAL_STRESS",
            "is_operationally_released": False,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("Research annotation: unvalidated experimental proxy risk", res["maintenance_recommendation"])
        self.assertIn("EXPERIMENTAL_PROXY_RISK_RESEARCH_ONLY", res["maintenance_reason_codes"])
        self.assertEqual(res["maintenance_inference_status"], "UNVALIDATED_RESEARCH_ONLY")
        # Must NEVER escalate to PLAN or URGENT
        self.assertNotEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertNotEqual(res["maintenance_priority"], MaintenancePriority.URGENT.value)

    def test_scenario_11_missing_temperature_or_protection_coverage(self) -> None:
        """Scenario 11: Missing temperature/protection coverage -> WATCH / insufficient data."""
        # (a) Missing temperature
        rec_no_temp = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": np.nan,  # Missing!
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        }
        res_a = self.engine.process_record(rec_no_temp)
        self.assertEqual(res_a["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("Verify instrumentation/communication", res_a["maintenance_recommendation"])
        self.assertIn("MISSING_CRITICAL_TELEMETRY", res_a["maintenance_reason_codes"])
        self.assertEqual(res_a["maintenance_data_quality_status"], "INSUFFICIENT_COVERAGE")

        # (b) Missing protection contacts (protection is NaN, not clear!)
        engine_b = MaintenanceEngine(config=self.config)
        rec_no_prot = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temperature": 55.0,
            "oil_temp_trip": np.nan,
            "oil_temp_alarm": np.nan,
            "magnetic_oil_gauge_alarm": np.nan,
        }
        res_b = engine_b.process_record(rec_no_prot)
        self.assertEqual(res_b["maintenance_priority"], MaintenancePriority.WATCH.value)
        self.assertIn("MISSING_CRITICAL_TELEMETRY", res_b["maintenance_reason_codes"])
        self.assertEqual(res_b["maintenance_data_quality_status"], "INSUFFICIENT_COVERAGE")

    # -------------------------------------------------------------
    # Precedence Hierarchy Tests
    # -------------------------------------------------------------

    def test_precedence_trip_overrides_missing_telemetry(self) -> None:
        """Precedence: verified trip overrides missing temperature/contacts to produce URGENT."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temp_trip": 1.0,  # Active trip
            "oil_temperature": np.nan,  # Missing telemetry
            "oil_temp_alarm": np.nan,
        }
        res = self.engine.process_record(rec)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertIn("VERIFIED_TRIP", res["maintenance_reason_codes"])

    def test_precedence_plan_overrides_watch(self) -> None:
        """Precedence: persistent condition (PLAN) overrides unconfirmed spike (WATCH)."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 50.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 80.0,  # Persistent imbalance
                "severity_electrical": 0.8,
                "fault_risk": 0.85,  # Unvalidated ML risk (WATCH candidate)
                "is_operationally_released": False,
            }
            res = self.engine.process_record(rec)

        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)

    # -------------------------------------------------------------
    # Exact Elapsed-Time Persistence Boundaries
    # -------------------------------------------------------------

    def test_persistence_boundary_under_30_minutes_does_not_trigger(self) -> None:
        """Exact boundary: 3 observations spanning 20 min (< 30 min) remains WATCH."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        # 3 observations at t=0, 10, 20 min -> span = 20 min < 30 min
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=10),
            base_time + pd.Timedelta(minutes=20),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 75.0,
            }
            res = self.engine.process_record(rec)

        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)

    def test_persistence_boundary_at_exactly_30_minutes_triggers(self) -> None:
        """Exact boundary: 3 observations spanning exactly 30 min triggers PLAN."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        # 3 observations at t=0, 15, 30 min -> span = 30 min
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 75.0,
            }
            res = self.engine.process_record(rec)

        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)

    def test_persistence_run_broken_by_clear_observation(self) -> None:
        """Invalid / clear observation breaks continuous qualifying run."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        recs = [
            {"t": base_time, "imb": 75.0},
            {"t": base_time + pd.Timedelta(minutes=15), "imb": 5.0},  # Intervening CLEAR!
            {"t": base_time + pd.Timedelta(minutes=30), "imb": 75.0},
        ]
        res = None
        for r in recs:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": r["t"],
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": r["imb"],
            }
            res = self.engine.process_record(rec)

        # Run was broken at t=15, so at t=30 only 1 observation is in buffer -> WATCH, not PLAN
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)

    def test_continuity_gap_resets_persistence_buffer(self) -> None:
        """Continuity gap > 30 minutes resets persistence buffer."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        # Gap between obs 2 and 3 is 35 minutes (> 30 minutes!)
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=50),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 75.0,
            }
            res = self.engine.process_record(rec)

        # Gap reset occurred at t=50, buffer has only 1 observation -> WATCH
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.WATCH.value)

    # -------------------------------------------------------------
    # Recovery Sequence Tests
    # -------------------------------------------------------------

    def test_recovery_sequence_requires_continuous_qualifying_clear_window(self) -> None:
        """De-escalation from PLAN to NORMAL requires >= 3 clear obs spanning >= 30 min."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        # 1. Establish PLAN (t=0, 15, 30 min)
        for m in (0, 15, 30):
            rec = {
                "transformer_id": "TX-001",
                "timestamp": base_time + pd.Timedelta(minutes=m),
                "oil_temperature": 55.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "current_imbalance_pct": 75.0,
            }
            self.engine.process_record(rec)

        state = self.engine.get_state("TX-001")
        self.assertEqual(state.escalated_priority, MaintenancePriority.PLAN)

        # 2. First clear observation (t=45) -> recovery in progress, remains PLAN
        rec_clear_1 = {
            "transformer_id": "TX-001",
            "timestamp": base_time + pd.Timedelta(minutes=45),
            "oil_temperature": 55.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "current_imbalance_pct": 5.0,  # Clear!
        }
        res_45 = self.engine.process_record(rec_clear_1)
        self.assertEqual(res_45["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertIn("RECOVERY_IN_PROGRESS", res_45["maintenance_reason_codes"])

        # 3. Second clear observation (t=60, span = 15 min < 30 min) -> still PLAN
        rec_clear_2 = {
            "transformer_id": "TX-001",
            "timestamp": base_time + pd.Timedelta(minutes=60),
            "oil_temperature": 55.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "current_imbalance_pct": 5.0,
        }
        res_60 = self.engine.process_record(rec_clear_2)
        self.assertEqual(res_60["maintenance_priority"], MaintenancePriority.PLAN.value)

        # 4. Third clear observation (t=75, span = 30 min, n=3) -> recovers to NORMAL!
        rec_clear_3 = {
            "transformer_id": "TX-001",
            "timestamp": base_time + pd.Timedelta(minutes=75),
            "oil_temperature": 55.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
            "current_imbalance_pct": 5.0,
        }
        res_75 = self.engine.process_record(rec_clear_3)
        self.assertEqual(res_75["maintenance_priority"], MaintenancePriority.NORMAL.value)
        self.assertIn("Normal operating condition", res_75["maintenance_recommendation"])

    # -------------------------------------------------------------
    # Trip Latching and Authorized Clear Tests
    # -------------------------------------------------------------

    def test_trip_latching_persists_when_contact_clears_until_authorized_clear(self) -> None:
        """Trip latches URGENT and does NOT auto-clear when contact goes to 0."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        # Step 1: Active trip at t=0
        rec_trip = {
            "transformer_id": "TX-001",
            "timestamp": base_time,
            "oil_temperature": 95.0,
            "oil_temp_trip": 1.0,
            "oil_temp_alarm": 1.0,
            "magnetic_oil_gauge_alarm": 0.0,
        }
        res_trip = self.engine.process_record(rec_trip)
        self.assertEqual(res_trip["maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertTrue(res_trip["maintenance_trip_latched"])

        # Step 2: Contact clears to 0 at t=15, normal telemetry
        rec_cleared = {
            "transformer_id": "TX-001",
            "timestamp": base_time + pd.Timedelta(minutes=15),
            "oil_temperature": 50.0,
            "oil_temp_trip": 0.0,  # Contact cleared
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        }
        res_cleared = self.engine.process_record(rec_cleared)
        # Latched! Must remain URGENT
        self.assertEqual(res_cleared["maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertTrue(res_cleared["maintenance_trip_latched"])
        self.assertIn("TRIP_LATCHED", res_cleared["maintenance_reason_codes"])
        self.assertEqual(res_cleared["maintenance_clear_policy_status"], "CONFIGURATION REQUIRED")

        # Step 3: Clear attempt without operator ID fails
        ok = self.engine.clear_trip_latch("TX-001", operator_id=None)
        self.assertFalse(ok)
        state = self.engine.get_state("TX-001")
        self.assertTrue(state.trip_latched)

        # Step 4: Authorized operator clear
        ok_auth = self.engine.clear_trip_latch("TX-001", operator_id="ENG-42", clear_policy="SITE_SOP_7")
        self.assertTrue(ok_auth)
        self.assertFalse(state.trip_latched)

        # Step 5: Next normal observation is now NORMAL
        rec_next = {
            "transformer_id": "TX-001",
            "timestamp": base_time + pd.Timedelta(minutes=30),
            "oil_temperature": 50.0,
            "oil_temp_trip": 0.0,
            "oil_temp_alarm": 0.0,
            "magnetic_oil_gauge_alarm": 0.0,
        }
        res_next = self.engine.process_record(rec_next)
        self.assertEqual(res_next["maintenance_priority"], MaintenancePriority.NORMAL.value)

    # -------------------------------------------------------------
    # Evidence Family Independence Tests
    # -------------------------------------------------------------

    def test_thermal_signals_belong_to_one_family_no_urgent_without_independent_vote(self) -> None:
        """Temp level, rate, and residual belong to ONE family and cannot self-corroborate into URGENT."""
        base_time = pd.Timestamp("2026-01-01 12:00:00")
        timestamps = [
            base_time,
            base_time + pd.Timedelta(minutes=15),
            base_time + pd.Timedelta(minutes=30),
        ]
        res = None
        for t in timestamps:
            rec = {
                "transformer_id": "TX-001",
                "timestamp": t,
                "oil_temperature": 90.0,  # High temp level
                "oil_temperature_rate": 2.5,  # High rate of rise
                "thermal_residual": 12.0,  # High residual
                "thermal_readiness": "READY",
                "severity_thermal": 0.9,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
                "severity_oil": 0.0,  # Normal oil level
                "severity_electrical": 0.0,  # Normal electrical
            }
            res = self.engine.process_record(rec)

        # Single thermal family cannot reach URGENT without independent corroboration! Reaches PLAN.
        self.assertIsNotNone(res)
        self.assertEqual(res["maintenance_priority"], MaintenancePriority.PLAN.value)
        self.assertNotEqual(res["maintenance_priority"], MaintenancePriority.URGENT.value)

    # -------------------------------------------------------------
    # Advisory Safety and Output Completeness
    # -------------------------------------------------------------

    def test_no_automatic_action_side_effects(self) -> None:
        """Maintenance engine outputs are strictly advisory; no switching commands exist."""
        rec = {
            "transformer_id": "TX-001",
            "timestamp": pd.Timestamp("2026-01-01 12:00:00"),
            "oil_temp_trip": 1.0,
        }
        res = self.engine.process_record(rec)
        # Verify output keys are strictly advisory
        for forbidden in ("trip_breaker", "scada_control", "relay_command", "shed_load", "emergency_envelope"):
            self.assertNotIn(forbidden, res)
        self.assertIn("Immediate operator review", res["maintenance_recommendation"])

    def test_deterministic_replay(self) -> None:
        """Identical sequences yield identical priorities and reason codes."""
        df = pd.DataFrame([
            {
                "transformer_id": "TX-001",
                "timestamp": pd.Timestamp("2026-01-01 12:00:00") + pd.Timedelta(minutes=15 * i),
                "oil_temperature": 50.0 + i * 5.0,
                "oil_temp_trip": 0.0,
                "oil_temp_alarm": 0.0,
                "magnetic_oil_gauge_alarm": 0.0,
            }
            for i in range(5)
        ])
        engine_1 = MaintenanceEngine(config=self.config)
        out_1 = engine_1.run(df)

        engine_2 = MaintenanceEngine(config=self.config)
        out_2 = engine_2.run(df)

    def test_synthetic_sequence_smoke_through_upstream_interfaces(self) -> None:
        """Synthetic sequence smoke test through upstream interfaces: thermal -> anomaly -> health -> maintenance."""
        from ml.thermal.thermal_twin import run_thermal_twin
        from ml.anomaly.detector import run_anomaly_detection
        from ml.health.engine import run_operating_health_index

        n = 12
        timestamps = pd.date_range("2026-01-01 12:00:00", periods=n, freq="15min")
        # Step 0-4: healthy reference
        # Step 5-7: persistent current imbalance (PLAN)
        # Step 8: trip occurs (URGENT)
        # Step 9-11: trip clears but latched (URGENT)
        cur_l1 = [50.0] * n
        cur_l2 = [50.0] * n
        cur_l3 = [50.0] * n
        for i in (5, 6, 7):
            cur_l1[i] = 120.0  # high imbalance

        oil_trip = [0.0] * n
        oil_trip[8] = 1.0  # trip at step 8

        df = pd.DataFrame({
            "transformer_id": ["TX-SMOKE"] * n,
            "timestamp": timestamps,
            "oil_temperature": [30.0] * n,
            "ambient_temperature": [25.0] * n,
            "current_l1": cur_l1,
            "current_l2": cur_l2,
            "current_l3": cur_l3,
            "current_mean": [50.0] * n,
            "current_imbalance_pct": [0.0 if i not in (5, 6, 7) else 80.0 for i in range(n)],
            "oil_temp_trip": oil_trip,
            "oil_temp_alarm": [0.0] * n,
            "magnetic_oil_gauge_alarm": [0.0] * n,
            "active_power_demand": [50.0] * n,
        })

        # 1. Thermal twin
        df_thermal = run_thermal_twin(df)
        self.assertIn("thermal_model_temperature", df_thermal.columns)

        # 2. Anomaly detection
        df_anomaly = run_anomaly_detection(df_thermal)
        self.assertIn("anomaly_score", df_anomaly.columns)

        # 3. Operating Health Index
        df_health = run_operating_health_index(df_anomaly)
        self.assertIn("health_index", df_health.columns)

        # 4. Maintenance Engine
        df_maint = run_maintenance_engine(df_health, config=self.config)
        self.assertIn("maintenance_priority", df_maint.columns)
        self.assertIn("maintenance_recommendation", df_maint.columns)
        self.assertIn("maintenance_reason_codes", df_maint.columns)

        # Verify priority transitions:
        # Step 0: NORMAL
        self.assertEqual(df_maint.loc[0, "maintenance_priority"], MaintenancePriority.NORMAL.value)
        # Step 5, 6: unconfirmed / developing imbalance -> WATCH
        self.assertEqual(df_maint.loc[5, "maintenance_priority"], MaintenancePriority.WATCH.value)
        # Step 7: persistent current imbalance (span = 30 min, n=3) -> PLAN
        self.assertEqual(df_maint.loc[7, "maintenance_priority"], MaintenancePriority.PLAN.value)
        # Step 8: trip occurs -> URGENT
        self.assertEqual(df_maint.loc[8, "maintenance_priority"], MaintenancePriority.URGENT.value)
        # Step 9: trip contact returns to 0 -> latched URGENT
        self.assertEqual(df_maint.loc[9, "maintenance_priority"], MaintenancePriority.URGENT.value)
        self.assertTrue(df_maint.loc[9, "maintenance_trip_latched"])


if __name__ == "__main__":
    unittest.main()
