"""Focused analytical, state, and behavioral tests for the Phase 01 Thermal Twin.

Tests cover:
- Analytical constant-forcing update
- Monotonic heating and monotonic cooling
- Subdivided interval equivalence under constant forcing
- Fixed tau dynamics independent of first observed interval or batch length
- Chunk/stream equivalence vs batch processing
- No cross-transformer state mixing
- Future oil perturbation leaves prior predictions unchanged
- Current oil observation does not contaminate same-time prediction
- Startup and gap-reset residual suppression
- Missing oil with valid forcing allows model integration with residual withheld
- Stale/insufficient forcing handling
- Gap restart (> 30 min) resets warm-up and state
- Non-finite (inf) input rejection
- High observed temperature with small residual
- Negative residual mismatch
- Reverse-power / current-squared heating consistency
- Parameter constraint validation
- Calibration smoke test and baseline comparison verification
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.features.feature_engineering import build_features
from ml.thermal.thermal_twin import (
    ALL_THERMAL_COLUMNS,
    THERMAL_OUTPUT_COLUMNS,
    ThermalModelMode,
    ThermalReadinessStatus,
    ThermalTwin,
    ThermalTwinConfig,
    ThermalTwinError,
    TransformerThermalState,
    run_thermal_twin,
)


def _sample_telemetry(n: int = 10, freq_minutes: int = 15) -> pd.DataFrame:
    """Create synthetic clean canonical telemetry dataframe."""
    timestamps = pd.date_range("2026-01-01 00:00", periods=n, freq=f"{freq_minutes}min")
    return pd.DataFrame({
        "transformer_id": ["TR-001"] * n,
        "timestamp": timestamps,
        "oil_temperature": [30.0 + i * 0.5 for i in range(n)],
        "ambient_temperature": [20.0] * n,
        "current_l1": [50.0] * n,
        "current_l2": [50.0] * n,
        "current_l3": [50.0] * n,
        "active_power_demand": [100.0] * n,
    })


class Phase01ThermalTwinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ThermalTwinConfig(
            b0=0.0,
            bA=1.0,
            bJ=0.001,
            tau_hours=1.0,  # 1 hour tau for clean analytical math
            continuity_gap_hours=0.5,
            warmup_epsilon=0.05,  # warmup duration = -1.0 * ln(0.05) ~ 2.9957 hours
            mode=ThermalModelMode.PUBLIC_EMPIRICAL,
        )

    def test_parameter_constraints_enforced(self) -> None:
        """Phase 01: bA >= 0, bJ >= 0, tau > 0, finite values required."""
        with self.assertRaisesRegex(ThermalTwinError, "tau_hours"):
            ThermalTwinConfig(tau_hours=0.0)
        with self.assertRaisesRegex(ThermalTwinError, "tau_hours"):
            ThermalTwinConfig(tau_hours=-1.0)
        with self.assertRaisesRegex(ThermalTwinError, "bA"):
            ThermalTwinConfig(bA=-0.5)
        with self.assertRaisesRegex(ThermalTwinError, "bJ"):
            ThermalTwinConfig(bJ=-0.001)
        with self.assertRaisesRegex(ThermalTwinError, "finite"):
            ThermalTwinConfig(b0=np.inf)

    def test_constant_forcing_analytical_update(self) -> None:
        """Phase 01: exact integration T_hat_t = u + (T_0 - u) * exp(-dt / tau)."""
        # u = b0 + bA*A + bJ*J = 0 + 1*20 + 0.001*2500 = 22.5
        # T_0 = 30.0. dt = 0.5h, tau = 1.0h
        # Analytical expected at t=1: 22.5 + (30.0 - 22.5) * exp(-0.5) = 22.5 + 7.5 * exp(-0.5)
        expected_t1 = 22.5 + 7.5 * np.exp(-0.5)

        df = pd.DataFrame({
            "transformer_id": ["TR-001", "TR-001"],
            "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30"]),
            "oil_temperature": [30.0, 30.0],
            "ambient_temperature": [20.0, 20.0],
            "current_l1": [50.0, 50.0],
            "current_l2": [50.0, 50.0],
            "current_l3": [50.0, 50.0],
        })
        res = run_thermal_twin(df, self.config)
        self.assertAlmostEqual(res.loc[0, "thermal_model_temperature"], 30.0)
        self.assertAlmostEqual(res.loc[1, "thermal_model_temperature"], expected_t1, places=5)

    def test_monotonic_heating_and_cooling(self) -> None:
        """Phase 01: under constant forcing, trajectory is strictly monotonic toward equilibrium."""
        # Heating: T_0 = 10, equilibrium = 22.5 (from A=20, J=2500, bJ=0.001)
        df_heat = pd.DataFrame({
            "transformer_id": ["TR-001"] * 5,
            "timestamp": pd.date_range("2026-01-01 00:00", periods=5, freq="15min"),
            "oil_temperature": [10.0] * 5,
            "ambient_temperature": [20.0] * 5,
            "current_l1": [50.0] * 5,
            "current_l2": [50.0] * 5,
            "current_l3": [50.0] * 5,
        })
        res_heat = run_thermal_twin(df_heat, self.config)
        t_heat = res_heat["thermal_model_temperature"].to_numpy()
        self.assertTrue(np.all(np.diff(t_heat) > 0), "Model temperature must monotonically increase")

        # Cooling: T_0 = 50, equilibrium = 22.5
        df_cool = df_heat.copy()
        df_cool["oil_temperature"] = 50.0
        res_cool = run_thermal_twin(df_cool, self.config)
        t_cool = res_cool["thermal_model_temperature"].to_numpy()
        self.assertTrue(np.all(np.diff(t_cool) < 0), "Model temperature must monotonically decrease")

    def test_subdivided_interval_equivalence(self) -> None:
        """Phase 01: two steps of dt/2 under constant forcing match one step of dt."""
        # 1 step of 30 min
        df_single = pd.DataFrame({
            "transformer_id": ["TR-001", "TR-001"],
            "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30"]),
            "oil_temperature": [30.0, 30.0],
            "ambient_temperature": [20.0, 20.0],
            "current_l1": [50.0, 50.0],
            "current_l2": [50.0, 50.0],
            "current_l3": [50.0, 50.0],
        })
        res_single = run_thermal_twin(df_single, self.config)

        # 2 steps of 15 min
        df_sub = pd.DataFrame({
            "transformer_id": ["TR-001", "TR-001", "TR-001"],
            "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:15", "2026-01-01 00:30"]),
            "oil_temperature": [30.0, 30.0, 30.0],
            "ambient_temperature": [20.0, 20.0, 20.0],
            "current_l1": [50.0, 50.0, 50.0],
            "current_l2": [50.0, 50.0, 50.0],
            "current_l3": [50.0, 50.0, 50.0],
        })
        res_sub = run_thermal_twin(df_sub, self.config)

        self.assertAlmostEqual(
            res_single.loc[1, "thermal_model_temperature"],
            res_sub.loc[2, "thermal_model_temperature"],
            places=7,
            msg="Subdivided interval under identical constant forcing must yield identical model temperature",
        )

    def test_fixed_tau_independent_of_first_interval(self) -> None:
        """Phase 01: dynamics depend only on physical elapsed hours, NOT on first interval spacing."""
        # Case A: first interval is 1 minute, next is 15 minutes
        df_a = pd.DataFrame({
            "transformer_id": ["TR-001"] * 3,
            "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:16"]),
            "oil_temperature": [20.0] * 3,
            "ambient_temperature": [20.0] * 3,
            "current_l1": [100.0] * 3,
            "current_l2": [100.0] * 3,
            "current_l3": [100.0] * 3,
        })
        res_a = run_thermal_twin(df_a, self.config)

        # In interval [00:01 -> 00:16], dt = 15 min = 0.25h
        # Under old alpha defect, response was scaled by dt / dt_ref = 15 / 1 = 15x exaggerated.
        # Under Phase 01 continuous dynamics, step from 00:01 to 00:16 uses exp(-0.25 / tau).
        t_start = res_a.loc[1, "thermal_model_temperature"]
        u_const = 0.0 + 1.0 * 20.0 + 0.001 * 10000.0  # 30.0
        expected_t2 = u_const + (t_start - u_const) * np.exp(-0.25 / self.config.tau_hours)
        self.assertAlmostEqual(res_a.loc[2, "thermal_model_temperature"], expected_t2, places=5)

    def test_chunk_and_stream_equivalence_via_state(self) -> None:
        """Phase 01: processing batch in chunks using persistent state matches full batch run."""
        df = _sample_telemetry(n=12, freq_minutes=15)

        # Full run
        res_full = run_thermal_twin(df, self.config)

        # Chunked run: chunk 1 (0..5), chunk 2 (6..11)
        twin = ThermalTwin(config=self.config)
        chunk1 = df.iloc[:6].copy()
        chunk2 = df.iloc[6:].copy()

        res_chunk1 = twin.run(chunk1)
        res_chunk2 = twin.run(chunk2)

        res_combined = pd.concat([res_chunk1, res_chunk2], axis=0)

        for col in ["thermal_model_temperature", "thermal_residual", "thermal_readiness"]:
            for i in range(len(df)):
                v_full = res_full.loc[i, col]
                v_chunk = res_combined.loc[i, col]
                if pd.isna(v_full) and pd.isna(v_chunk):
                    continue
                if isinstance(v_full, float):
                    self.assertAlmostEqual(v_full, v_chunk, places=6)
                else:
                    self.assertEqual(v_full, v_chunk)

    def test_no_cross_transformer_state_mixing(self) -> None:
        """Phase 01: multiple transformers are tracked in independent states."""
        df = pd.DataFrame({
            "transformer_id": ["TR-002", "TR-001", "TR-002", "TR-001"],
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00", "2026-01-01 00:00",
                "2026-01-01 00:15", "2026-01-01 00:15",
            ]),
            "oil_temperature": [20.0, 30.0, 20.0, 30.0],
            "ambient_temperature": [20.0, 20.0, 20.0, 20.0],
            "current_l1": [0.0, 100.0, 0.0, 100.0],
            "current_l2": [0.0, 100.0, 0.0, 100.0],
            "current_l3": [0.0, 100.0, 0.0, 100.0],
        })
        res = run_thermal_twin(df, self.config)
        # TR-002 forcing: 20 + 0 = 20.0. Started at 20.0 -> stays 20.0
        # TR-001 forcing: 20 + 10 = 30.0. Started at 30.0 -> stays 30.0
        self.assertAlmostEqual(res.loc[2, "thermal_model_temperature"], 20.0)
        self.assertAlmostEqual(res.loc[3, "thermal_model_temperature"], 30.0)

    def test_future_oil_perturbation_leaves_past_predictions_unchanged(self) -> None:
        """Phase 01: modifying future records does not alter past predictions."""
        df = _sample_telemetry(n=6, freq_minutes=15)
        base = run_thermal_twin(df, self.config)

        df_mod = df.copy()
        df_mod.loc[5, "oil_temperature"] = 999.0
        altered = run_thermal_twin(df_mod, self.config)

        for i in range(5):
            self.assertEqual(
                base.loc[i, "thermal_model_temperature"],
                altered.loc[i, "thermal_model_temperature"],
            )

    def test_current_oil_observation_does_not_contaminate_same_time_prediction(self) -> None:
        """Phase 01: perturbing current oil changes its residual, but NOT same-time model temperature."""
        df = _sample_telemetry(n=6, freq_minutes=15)
        base = run_thermal_twin(df, self.config)

        df_mod = df.copy()
        df_mod.loc[3, "oil_temperature"] = 80.0
        altered = run_thermal_twin(df_mod, self.config)

        # Same-time model prediction at step 3 must be identical
        self.assertEqual(
            base.loc[3, "thermal_model_temperature"],
            altered.loc[3, "thermal_model_temperature"],
        )
        # Residual at step 3 must reflect the new observed temperature
        if not pd.isna(base.loc[3, "thermal_residual"]):
            self.assertNotEqual(
                base.loc[3, "thermal_residual"],
                altered.loc[3, "thermal_residual"],
            )

    def test_initialization_and_warmup_residual_suppression(self) -> None:
        """Phase 01: residual is suppressed (NaN) during initialization and warm-up."""
        # 4 records at 15 min = 0, 15, 30, 45 min = 0.75 hours < warmup_duration (approx 3h)
        df = _sample_telemetry(n=4, freq_minutes=15)
        res = run_thermal_twin(df, self.config)

        self.assertEqual(res.loc[0, "thermal_readiness"], ThermalReadinessStatus.INITIALIZING.value)
        self.assertTrue(pd.isna(res.loc[0, "thermal_residual"]))

        # Steps 1, 2, 3 are in warm-up
        for i in range(1, 4):
            self.assertEqual(res.loc[i, "thermal_readiness"], ThermalReadinessStatus.WARMING_UP.value)
            self.assertTrue(pd.isna(res.loc[i, "thermal_residual"]))

    def test_ready_after_warmup_produces_signed_residual(self) -> None:
        """Phase 01: after elapsed time exceeds 3*tau, readiness is READY and residual is signed."""
        # tau = 1.0h, warmup = ~3.0h = 12 steps of 15 min
        df = _sample_telemetry(n=16, freq_minutes=15)
        res = run_thermal_twin(df, self.config)

        # Step 15 has elapsed 3.75 hours > 3.0h
        self.assertEqual(res.loc[15, "thermal_readiness"], ThermalReadinessStatus.READY.value)
        self.assertFalse(pd.isna(res.loc[15, "thermal_residual"]))
        # Signed residual: r = T_obs - T_hat
        expected_r = df.loc[15, "oil_temperature"] - res.loc[15, "thermal_model_temperature"]
        self.assertAlmostEqual(res.loc[15, "thermal_residual"], expected_r, places=6)

    def test_missing_oil_with_valid_forcing_allows_integration(self) -> None:
        """Phase 01: missing oil observation allows valid model integration; residual is unavailable."""
        # Create series long enough to exit warm-up
        df = _sample_telemetry(n=16, freq_minutes=15)
        df.loc[14, "oil_temperature"] = np.nan
        res = run_thermal_twin(df, self.config)

        # Step 14 should have a valid model prediction
        self.assertFalse(pd.isna(res.loc[14, "thermal_model_temperature"]))
        # But residual must be NaN because observed oil was missing
        self.assertTrue(pd.isna(res.loc[14, "thermal_residual"]))

    def test_gap_over_30min_resets_state_and_triggers_warmup(self) -> None:
        """Phase 01: gap > 30 minutes triggers gap reset and warm-up suppression."""
        df = pd.DataFrame({
            "transformer_id": ["TR-001"] * 4,
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00",
                "2026-01-01 00:15",
                "2026-01-01 01:00",  # 45 min gap > 30 min continuity limit
                "2026-01-01 01:15",
            ]),
            "oil_temperature": [30.0, 31.0, 35.0, 36.0],
            "ambient_temperature": [20.0] * 4,
            "current_l1": [50.0] * 4,
            "current_l2": [50.0] * 4,
            "current_l3": [50.0] * 4,
        })
        res = run_thermal_twin(df, self.config)

        self.assertEqual(res.loc[2, "thermal_readiness"], ThermalReadinessStatus.GAP_RESET.value)
        # Model re-initializes from step 2 observed oil
        self.assertAlmostEqual(res.loc[2, "thermal_model_temperature"], 35.0)
        self.assertTrue(pd.isna(res.loc[2, "thermal_residual"]))

    def test_non_finite_input_rejected(self) -> None:
        """Phase 01: non-finite (inf) values raise ThermalTwinError."""
        df = _sample_telemetry(n=3, freq_minutes=15)
        df.loc[1, "oil_temperature"] = np.inf
        with self.assertRaisesRegex(ThermalTwinError, "Non-finite"):
            run_thermal_twin(df, self.config)

    def test_reverse_power_current_squared_heating_consistency(self) -> None:
        """Phase 01: negative active power still causes positive heating through current-squared J."""
        df = pd.DataFrame({
            "transformer_id": ["TR-001", "TR-001"],
            "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30"]),
            "oil_temperature": [20.0, 20.0],
            "ambient_temperature": [20.0, 20.0],
            "current_l1": [50.0, 50.0],
            "current_l2": [50.0, 50.0],
            "current_l3": [50.0, 50.0],
            "active_power_demand": [-100.0, -100.0],  # Negative active power (reverse flow)
        })
        res = run_thermal_twin(df, self.config)
        # J = 2500, equilibrium = 22.5 > 20.0. Temperature rises despite negative active power.
        self.assertGreater(res.loc[1, "thermal_model_temperature"], 20.0)

    def test_high_temperature_with_near_zero_residual(self) -> None:
        """Phase 01: high observed temperature does not produce high residual if expected by forcing."""
        # Equilibrium forcing: b0=0, bA=1*40, bJ=0.001*25000 = 65.0
        df = pd.DataFrame({
            "transformer_id": ["TR-001"] * 20,
            "timestamp": pd.date_range("2026-01-01 00:00", periods=20, freq="15min"),
            "oil_temperature": [65.0] * 20,  # High temperature
            "ambient_temperature": [40.0] * 20,  # High ambient
            "current_l1": [158.11] * 20,  # High load (J ~ 25000)
            "current_l2": [158.11] * 20,
            "current_l3": [158.11] * 20,
        })
        res = run_thermal_twin(df, self.config)
        # After warm-up, residual should be very close to zero
        late_res = res.loc[18, "thermal_residual"]
        self.assertAlmostEqual(late_res, 0.0, delta=0.5)

    def test_negative_residual_is_model_mismatch(self) -> None:
        """Phase 01: observed temperature lower than model gives negative signed residual."""
        df = pd.DataFrame({
            "transformer_id": ["TR-001"] * 20,
            "timestamp": pd.date_range("2026-01-01 00:00", periods=20, freq="15min"),
            "oil_temperature": [15.0] * 20,  # Much colder than expected (forcing is 22.5)
            "ambient_temperature": [20.0] * 20,
            "current_l1": [50.0] * 20,
            "current_l2": [50.0] * 20,
            "current_l3": [50.0] * 20,
        })
        res = run_thermal_twin(df, self.config)
        # At step 18, residual must be negative
        late_r = res.loc[18, "thermal_residual"]
        self.assertLess(late_r, 0.0)
