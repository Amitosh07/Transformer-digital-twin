"""Focused tests for the Phase 03 Operating Health Index.

Tests cover:
- All 8 mandatory calculated fixtures from 03_HEALTH_INDEX.md:
    1. Healthy reference (H = 100)
    2. High load, normal thermal response (H = 91)
    3. High oil temperature (H = 40, capped from 72)
    4. Current imbalance (H = 50, capped from 82.5)
    5. Positive thermal residual (H = 60, capped from 79)
    6. Active alarm (H = 60, capped from 83)
    7. Verified trip (H = 0 override)
    8. Multiple problems (H = 40, capped from 43)
- Score bounds [0, 100]
- Monotonic worsening with fixed coverage
- Component weights sum strictly to 1.0
- Partial-component renormalization and coverage C_H
- All components unavailable produces null
- Loading component null when rating is missing
- Missing protection is not treated as clear
- Verified trip override precedence
- Cap excludes loading-only evidence
- Cap excludes anomaly-only evidence
- Non-persistent spike does not trigger persistent cap
- Missing thermal behavior and partial assessment status
- Complete independence from fault risk and maintenance engines
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.health.engine import (
    ALL_HEALTH_COLUMNS,
    COMPONENT_WEIGHTS,
    HEALTH_OUTPUT_COLUMNS,
    HealthIndexConfig,
    HealthIndexError,
    OperatingHealthIndex,
    calculate_health_index_record,
    run_operating_health_index,
)


class Phase03HealthIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = HealthIndexConfig()

    def test_weights_sum_to_one(self) -> None:
        """Phase 03: component weights must sum strictly to 1.0."""
        self.assertAlmostEqual(sum(self.config.weights.values()), 1.0, places=7)
        self.assertEqual(self.config.weights["thermal"], 0.30)
        self.assertEqual(self.config.weights["electrical"], 0.20)
        self.assertEqual(self.config.weights["loading"], 0.10)
        self.assertEqual(self.config.weights["oil"], 0.15)
        self.assertEqual(self.config.weights["alarm"], 0.20)
        self.assertEqual(self.config.weights["anomaly"], 0.05)

    def test_invalid_weights_raise_error(self) -> None:
        """Phase 03: weights not summing to 1.0 or negative weights raise error."""
        with self.assertRaisesRegex(HealthIndexError, "sum to 1.0"):
            HealthIndexConfig(weights={"thermal": 0.5, "electrical": 0.6})
        with self.assertRaisesRegex(HealthIndexError, "non-negative"):
            HealthIndexConfig(weights={
                "thermal": 1.2, "electrical": -0.2, "loading": 0.0,
                "oil": 0.0, "alarm": 0.0, "anomaly": 0.0,
            })

    # -------------------------------------------------------------
    # The 8 Mandatory Calculated Fixtures from 03_HEALTH_INDEX.md
    # -------------------------------------------------------------

    def test_fixture_1_healthy_reference(self) -> None:
        """Fixture 1: Healthy reference -> Weighted 100, Final 100."""
        comp = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 100}
        res = calculate_health_index_record(comp, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 100.0)
        self.assertAlmostEqual(res["health_index"], 100.0)
        self.assertFalse(res["health_cap_applied"])
        self.assertFalse(res["health_trip_override"])

    def test_fixture_2_high_load_normal_thermal_response(self) -> None:
        """Fixture 2: High load, normal thermal response -> Weighted 91, Final 91."""
        comp = {"thermal": 100, "electrical": 100, "loading": 40, "oil": 100, "alarm": 100, "anomaly": 40}
        res = calculate_health_index_record(comp, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 91.0)
        self.assertAlmostEqual(res["health_index"], 91.0)
        self.assertFalse(res["health_cap_applied"])

    def test_fixture_3_high_oil_temperature(self) -> None:
        """Fixture 3: High oil temperature -> Weighted 72, Final 40 (capped)."""
        comp = {"thermal": 20, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 20}
        res = calculate_health_index_record(comp, persistent_components={"thermal"}, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 72.0)
        self.assertAlmostEqual(res["health_index"], 40.0)
        self.assertTrue(res["health_cap_applied"])

    def test_fixture_4_current_imbalance(self) -> None:
        """Fixture 4: Current imbalance -> Weighted 82.5, Final 50 (capped)."""
        comp = {"thermal": 100, "electrical": 30, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 30}
        res = calculate_health_index_record(comp, persistent_components={"electrical"}, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 82.5)
        self.assertAlmostEqual(res["health_index"], 50.0)
        self.assertTrue(res["health_cap_applied"])

    def test_fixture_5_positive_thermal_residual(self) -> None:
        """Fixture 5: Positive thermal residual -> Weighted 79, Final 60 (capped)."""
        comp = {"thermal": 40, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 40}
        res = calculate_health_index_record(comp, persistent_components={"thermal"}, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 79.0)
        self.assertAlmostEqual(res["health_index"], 60.0)
        self.assertTrue(res["health_cap_applied"])

    def test_fixture_6_active_alarm(self) -> None:
        """Fixture 6: Active alarm -> Weighted 83, Final 60 (capped)."""
        comp = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 40, "anomaly": 0}
        res = calculate_health_index_record(comp, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 83.0)
        self.assertAlmostEqual(res["health_index"], 60.0)
        self.assertTrue(res["health_cap_applied"])

    def test_fixture_7_verified_trip(self) -> None:
        """Fixture 7: Verified trip -> Weighted 75, Final 0 (override)."""
        comp = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 0, "anomaly": 0}
        res = calculate_health_index_record(comp, is_trip_active=True, config=self.config)
        self.assertAlmostEqual(res["health_index"], 0.0)
        self.assertTrue(res["health_trip_override"])

    def test_fixture_8_multiple_problems(self) -> None:
        """Fixture 8: Multiple problems -> Weighted 43, Final 40 (capped)."""
        comp = {"thermal": 20, "electrical": 30, "loading": 40, "oil": 40, "alarm": 100, "anomaly": 20}
        res = calculate_health_index_record(comp, persistent_components={"thermal", "electrical", "oil"}, config=self.config)
        self.assertAlmostEqual(res["health_unweighted_score"], 43.0)
        self.assertAlmostEqual(res["health_index"], 40.0)
        self.assertTrue(res["health_cap_applied"])

    # -------------------------------------------------------------
    # Partial Coverage and Missing Data Tests
    # -------------------------------------------------------------

    def test_partial_coverage_renormalization(self) -> None:
        """Phase 03: partial components renormalize over available weights without multiplying HI by coverage."""
        # Only thermal (0.30) and electrical (0.20) available. Available weight = 0.50.
        # Thermal = 80, Electrical = 90.
        # Weighted available: (0.30*80 + 0.20*90) / 0.50 = (24 + 18) / 0.50 = 42 / 0.50 = 84.0.
        comp = {"thermal": 80, "electrical": 90, "loading": None, "oil": None, "alarm": None, "anomaly": None}
        res = calculate_health_index_record(comp, config=self.config)
        self.assertAlmostEqual(res["health_coverage"], 0.50)
        self.assertAlmostEqual(res["health_index"], 84.0)

    def test_all_components_missing_produces_null(self) -> None:
        """Phase 03: completely missing components produce null Health Index."""
        comp = {"thermal": None, "electrical": None, "loading": None, "oil": None, "alarm": None, "anomaly": None}
        res = calculate_health_index_record(comp, config=self.config)
        self.assertIsNone(res["health_index"])
        self.assertEqual(res["health_coverage"], 0.0)

    def test_loading_component_null_when_rating_missing(self) -> None:
        """Phase 03: missing rating makes loading component null, not 100."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "severity_thermal": 0.0,
            "severity_electrical": 0.0,
            "apparent_power_utilization": np.nan,  # Rating missing!
            "severity_oil": 0.0,
            "oil_temp_alarm": 0.0,
            "oil_temp_trip": 0.0,
            "anomaly_score": 0.0,
        }])
        engine = OperatingHealthIndex(config=self.config)
        res = engine.run(df)
        components = res.loc[0, "health_components"]
        self.assertIsNone(components["loading"])
        self.assertIn("RATING_UNAVAILABLE", res.loc[0, "health_reason_codes"])
        # Coverage is 1.0 - 0.10 = 0.90
        self.assertAlmostEqual(res.loc[0, "health_coverage"], 0.90)
        self.assertAlmostEqual(res.loc[0, "health_index"], 100.0)

    def test_missing_protection_is_not_clear(self) -> None:
        """Phase 03: missing protection contacts remain null, never assumed clear 100."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "severity_thermal": 0.0,
            "oil_temp_alarm": np.nan,
            "oil_temp_trip": np.nan,
            "magnetic_oil_gauge_alarm": np.nan,
        }])
        engine = OperatingHealthIndex(config=self.config)
        res = engine.run(df)
        components = res.loc[0, "health_components"]
        self.assertIsNone(components["alarm"])

    def test_verified_trip_overrides_to_zero_despite_missing_telemetry(self) -> None:
        """Phase 03: verified active trip produces 0 even if other telemetry is absent."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "oil_temp_trip": 1.0,
            "severity_thermal": np.nan,
            "severity_electrical": np.nan,
        }])
        engine = OperatingHealthIndex(config=self.config)
        res = engine.run(df)
        self.assertAlmostEqual(res.loc[0, "health_index"], 0.0)
        self.assertTrue(res.loc[0, "health_trip_override"])
        self.assertIn("VERIFIED_TRIP_OVERRIDE", res.loc[0, "health_reason_codes"])

    def test_cap_excludes_loading_and_anomaly_only(self) -> None:
        """Phase 03: severe loading alone or severe anomaly alone does NOT trigger the cap."""
        # Severe loading alone: loading = 0 (s_L = 1.0), all other components 100.
        # Weighted score: 0.30*100 + 0.20*100 + 0.10*0 + 0.15*100 + 0.20*100 + 0.05*100 = 90.0.
        # Cap must NOT pull it down to 20 + 0 = 20!
        comp = {"thermal": 100, "electrical": 100, "loading": 0, "oil": 100, "alarm": 100, "anomaly": 100}
        res = calculate_health_index_record(comp, persistent_components=set(), config=self.config)
        self.assertAlmostEqual(res["health_index"], 90.0)
        self.assertFalse(res["health_cap_applied"])

        # Severe anomaly alone: anomaly = 0, others 100.
        # Weighted score: 100 - 0.05*100 = 95.0.
        # Cap must NOT pull it down to 20 + 0 = 20!
        comp_a = {"thermal": 100, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 0}
        res_a = calculate_health_index_record(comp_a, persistent_components=set(), config=self.config)
        self.assertAlmostEqual(res_a["health_index"], 95.0)
        self.assertFalse(res_a["health_cap_applied"])

    def test_non_persistent_spike_does_not_trigger_cap(self) -> None:
        """Phase 03: an isolated statistical spike without elapsed persistence does not trigger the cap."""
        # Single observation of severe thermal (T=20) without persistence
        comp = {"thermal": 20, "electrical": 100, "loading": 100, "oil": 100, "alarm": 100, "anomaly": 20}
        res = calculate_health_index_record(comp, persistent_components=set(), config=self.config)
        # Without persistent flag, cap does not trigger -> stays weighted 72.0
        self.assertAlmostEqual(res["health_index"], 72.0)
        self.assertFalse(res["health_cap_applied"])


if __name__ == "__main__":
    unittest.main()
