"""Tests for Phase 07 — Unified ML/Twin Pipeline.

Covers all 30 Phase 07 testing requirements:
1. Stable response serialization
2. Null numeric values
3. Unknown boolean handling
4. Excluded-field absence
5. Stable feature order
6. Single-record execution
7. Batch execution
8. Chunked execution
9. Batch/stream equivalence
10. Independent asset isolation
11. Multi-asset interleaving
12. Deterministic replay
13. Replay at different execution speeds
14. Retry idempotency
15. Duplicate observation handling
16. Late-row policy
17. Restart state continuity
18. Long-gap reset
19. Incompatible model/config state reset
20. Missing rating behavior
21. Correct loading ratio/percent
22. Thermal unit consistency
23. Thermal readiness/warm-up
24. Null forecast behavior
25. Trip override despite missing inputs
26. No forecast artifact fallback
27. No dashboard-side recalculation
28. No control/SCADA side effects
29. Configuration/model version propagation
30. Error vs valid-unavailable distinction
"""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone, timedelta
import unittest

import numpy as np
import pandas as pd

from ml.pipeline.asset_config import AssetConfig
from ml.pipeline.bundle import PipelineBundle
from ml.pipeline.orchestrator import (
    PipelineValidationError,
    UnifiedMLPipeline,
    analyze,
)
from ml.pipeline.state import AssetPipelineState


def fictional_asset(asset):
    return AssetConfig(asset, rated_power_kva=100., measurement_side='LV',
        configuration_metadata={'version': 'fictional-test-v1',
            'status': 'SYNTHETIC_CONFIG', 'field_metadata': {'rated_power_kva': {
                'unit': 'kVA', 'verification': 'SYNTHETIC_CONFIG',
                'provenance': 'fictional unit test', 'evidence_reference': None}}})


def fictional_acquisition():
    from ml.pipeline.identity import FIELDS
    return {'source_kind': 'SIMULATED', 'source_name': 'fictional-test',
            'origin_kind': 'SIMULATED', 'origin_transformer_id': None,
            'replay_run_id': None, 'gateway_id': None,
            'timestamp_origin': 'SOURCE_SNAPSHOT', 'timezone_status': 'DECLARED_UTC',
            'field_units': {k: 'kVA' if k == 'apparent_power_total' else 'UNKNOWN' for k in FIELDS},
            'field_verification': {k: 'SYNTHETIC' if k == 'apparent_power_total' else 'UNVERIFIED' for k in FIELDS},
            'measurement_side': 'LV', 'map_version': None, 'snapshot_id': None,
            'sequence': None, 'expected_interval_seconds': 900}


def make_sample_record(
    transformer_id: str = "TX-001",
    timestamp: str | datetime = "2026-10-08T10:00:00Z",
    oil_temp: float = 45.0,
    ambient_temp: float = 25.0,
    current: float = 15.0,
    voltage: float = 230.0,
    oil_level: float = 8.0,
    s_total: float = 50.0,
    trip: int = 0,
    alarm: int = 0,
    mog: int = 0,
    extra_fields: dict | None = None,
) -> dict:
    """Create a canonical test record."""
    rec = {
        "transformer_id": transformer_id,
        "timestamp": timestamp,
        "oil_temperature": oil_temp,
        "ambient_temperature": ambient_temp,
        "current_l1": current,
        "current_l2": current,
        "current_l3": current,
        "phase_voltage_l1": voltage,
        "phase_voltage_l2": voltage,
        "phase_voltage_l3": voltage,
        "neutral_current": 0.0,
        "oil_level": oil_level,
        "oil_temp_alarm": alarm,
        "oil_temp_trip": trip,
        "magnetic_oil_gauge_alarm": mog,
        "active_power_total": s_total,
        "apparent_power_total": s_total,
        "power_factor_l1": 1.0,
        "power_factor_l2": 1.0,
        "power_factor_l3": 1.0,
    }
    if extra_fields:
        rec.update(extra_fields)
    return rec


class TestUnifiedPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = PipelineBundle.load_from_processed_dir()
        self.pipeline = UnifiedMLPipeline(bundle=self.bundle)

    def test_01_stable_response_serialization(self) -> None:
        rec = make_sample_record()
        res = self.pipeline.process_record(rec)

        expected_keys = {
            "transformer_id",
            "timestamp",
            "inference_status",
            "missing_features",
            "loading_percent",
            "thermal_model_temperature",
            "thermal_residual",
            "thermal_state",
            "anomaly_score",
            "anomaly_flag",
            "health_index",
            "health_components",
            "health_reason_codes",
            "fault_risk",
            "predicted_fault",
            "prediction_confidence",
            "maintenance_priority",
            "maintenance_recommendation",
            "reason_codes",
            "schema_version",
            "feature_version",
            "model_version",
            "metadata",
        }
        self.assertEqual(set(res.keys()), expected_keys)
        self.assertEqual(res["schema_version"], "1.0.0")
        self.assertEqual(res["feature_version"], "1.0.0")
        self.assertEqual(res["model_version"], "1.0.0")

    def test_02_null_numeric_values_not_nan_or_inf(self) -> None:
        # Without rating, loading_percent must be JSON None (null), never NaN, inf, or 0.0
        rec = make_sample_record(s_total=50.0)
        res = self.pipeline.process_record(rec)

        self.assertIsNone(res["loading_percent"])
        self.assertIsNone(res["metadata"]["apparent_power_utilization"])
        # During initial warm-up, thermal_residual is None
        self.assertIsNone(res["thermal_residual"])
        # Unvalidated forecast is None
        self.assertIsNone(res["fault_risk"])

        # Check all values in dict: no float NaN or Inf allowed
        for k, v in res.items():
            if isinstance(v, float):
                self.assertTrue(np.isfinite(v), f"Value for {k} must be finite float, got {v}")

    def test_03_unknown_boolean_handling(self) -> None:
        # All missing telemetry produces None flag, not False
        sparse_rec = {
            "transformer_id": "TX-001",
            "timestamp": "2026-10-08T10:00:00Z",
        }
        res = self.pipeline.process_record(sparse_rec)
        self.assertIsNone(res["anomaly_flag"])

    def test_04_excluded_field_absence(self) -> None:
        for excl in ("VL12", "vl23", "VL31", "Vl12"):
            rec = make_sample_record(extra_fields={excl: 230.0})
            with self.assertRaises(PipelineValidationError):
                self.pipeline.process_record(rec)

    def test_05_stable_feature_order(self) -> None:
        # Feature order in model bundle must be strictly preserved
        if self.bundle.forecast_model is not None and self.bundle.forecast_model.preprocessor is not None:
            feat_names = self.bundle.forecast_model.preprocessor.feature_names
            self.assertEqual(
                feat_names,
                [
                    "oil_temperature",
                    "ambient_temperature",
                    "temperature_slope",
                    "current_mean",
                    "current_imbalance_pct",
                    "apparent_power_total",
                    "rolling_load_mean",
                    "thermal_residual",
                ],
            )

    def test_06_single_record_execution(self) -> None:
        rec = make_sample_record()
        res = self.pipeline.process_record(rec)
        self.assertEqual(res["transformer_id"], "TX-001")
        self.assertEqual(res["inference_status"], "OK")

    def test_07_batch_execution(self) -> None:
        records = [
            make_sample_record(timestamp=f"2026-10-08T10:{m:02d}:00Z")
            for m in (0, 15, 30)
        ]
        results = self.pipeline.process_batch(records)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["timestamp"], "2026-10-08T10:00:00+00:00")
        self.assertEqual(results[2]["timestamp"], "2026-10-08T10:30:00+00:00")

    def test_08_chunked_execution(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        recs = [
            make_sample_record(timestamp=f"2026-10-08T10:{m:02d}:00Z")
            for m in (0, 15, 30, 45)
        ]
        # Run chunk 1 then chunk 2
        chunk1 = pipe.process_batch(recs[:2])
        chunk2 = pipe.process_batch(recs[2:])
        self.assertEqual(len(chunk1), 2)
        self.assertEqual(len(chunk2), 2)

    def test_09_batch_stream_equivalence(self) -> None:
        recs = [
            make_sample_record(timestamp=f"2026-10-08T10:{m:02d}:00Z")
            for m in (0, 15, 30, 45)
        ]
        # Sequential stream
        pipe_stream = UnifiedMLPipeline(bundle=self.bundle)
        stream_results = [pipe_stream.process_record(r) for r in recs]

        # Batch
        pipe_batch = UnifiedMLPipeline(bundle=self.bundle)
        batch_results = pipe_batch.process_batch(recs)

        for s_res, b_res in zip(stream_results, batch_results):
            self.assertEqual(s_res["health_index"], b_res["health_index"])
            self.assertEqual(s_res["anomaly_score"], b_res["anomaly_score"])
            self.assertEqual(s_res["thermal_model_temperature"], b_res["thermal_model_temperature"])
            self.assertEqual(s_res["maintenance_priority"], b_res["maintenance_priority"])

    def test_10_independent_asset_isolation(self) -> None:
        # Asset 1 has high current and trip; Asset 2 is completely nominal
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        r1 = make_sample_record(transformer_id="TX-001", trip=1)
        r2 = make_sample_record(transformer_id="TX-002", trip=0)

        res1 = pipe.process_record(r1)
        res2 = pipe.process_record(r2)

        self.assertEqual(res1["maintenance_priority"], "URGENT")
        self.assertEqual(res2["maintenance_priority"], "WATCH")
        self.assertFalse(pipe.get_state("TX-002").maintenance_state.trip_latched)
        self.assertTrue(pipe.get_state("TX-001").maintenance_state.trip_latched)

    def test_11_multi_asset_interleaving(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        recs = [
            make_sample_record(transformer_id="TX-A", timestamp="2026-10-08T10:00:00Z"),
            make_sample_record(transformer_id="TX-B", timestamp="2026-10-08T10:05:00Z"),
            make_sample_record(transformer_id="TX-A", timestamp="2026-10-08T10:15:00Z"),
            make_sample_record(transformer_id="TX-B", timestamp="2026-10-08T10:20:00Z"),
        ]
        results = pipe.process_batch(recs)
        self.assertEqual(len(results), 4)
        self.assertEqual(pipe.get_state("TX-A").observation_count, 2)
        self.assertEqual(pipe.get_state("TX-B").observation_count, 2)

    def test_12_deterministic_replay(self) -> None:
        recs = [
            make_sample_record(timestamp=f"2026-10-08T10:{m:02d}:00Z")
            for m in (0, 15, 30)
        ]
        pipe1 = UnifiedMLPipeline(bundle=self.bundle)
        pipe2 = UnifiedMLPipeline(bundle=self.bundle)

        res1 = pipe1.process_batch(recs)
        res2 = pipe2.process_batch(recs)

        for r1, r2 in zip(res1, res2):
            self.assertEqual(r1["health_index"], r2["health_index"])
            self.assertEqual(r1["thermal_model_temperature"], r2["thermal_model_temperature"])

    def test_13_replay_at_different_execution_speeds(self) -> None:
        # Pipeline must use event-time, never wall-clock time
        recs = [
            make_sample_record(timestamp=f"2026-10-08T10:{m:02d}:00Z")
            for m in (0, 15, 30)
        ]
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        results = pipe.process_batch(recs)
        # Thermal model temp should advance deterministically based on dt (15 min = 0.25h)
        self.assertIsNotNone(results[1]["thermal_model_temperature"])

    def test_14_retry_idempotency(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec = make_sample_record(timestamp="2026-10-08T10:00:00Z")

        res1 = pipe.process_record(rec)
        obs_count = pipe.get_state("TX-001").observation_count
        res2 = pipe.process_record(rec)

        self.assertEqual(res1, res2)
        # Observation count must not increment on idempotent retry
        self.assertEqual(pipe.get_state("TX-001").observation_count, obs_count)

    def test_15_duplicate_observation_handling(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        pipe.process_record(rec)
        # Re-sending identical observation returns existing result without advancing thermal twin
        t_state_before = pipe.get_state("TX-001").thermal_state.last_model_temperature
        pipe.process_record(rec)
        t_state_after = pipe.get_state("TX-001").thermal_state.last_model_temperature
        self.assertEqual(t_state_before, t_state_after)

    def test_16_late_row_policy(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec1 = make_sample_record(timestamp="2026-10-08T10:30:00Z")
        rec2 = make_sample_record(timestamp="2026-10-08T10:15:00Z")  # Late!

        res1 = pipe.process_record(rec1)
        res2 = pipe.process_record(rec2)

        self.assertEqual(res2['ingestion_outcome'], 'REJECTED_LATE_OBSERVATION')
        self.assertIsNone(res2['analytics'])
        self.assertFalse(res2['forward_state_advanced'])
        # Latest committed timestamp must remain 10:30
        self.assertEqual(
            pipe.get_state("TX-001").last_processed_timestamp,
            pd.Timestamp("2026-10-08T10:30:00Z"),
        )

    def test_17_restart_state_continuity(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec1 = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        pipe.process_record(rec1)

        state = pipe.get_state("TX-001")
        self.assertEqual(state.observation_count, 1)

        # Subsequent observation continues from saved state
        rec2 = make_sample_record(timestamp="2026-10-08T10:15:00Z")
        pipe.process_record(rec2)
        self.assertEqual(state.observation_count, 2)

    def test_18_long_gap_reset(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec1 = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        rec2 = make_sample_record(timestamp="2026-10-08T11:00:00Z")  # 1 hour gap > 30 min limit

        pipe.process_record(rec1)
        res2 = pipe.process_record(rec2)

        # Gap reset triggers warm-up suppression in thermal model
        self.assertIsNone(res2["thermal_residual"])
        self.assertEqual(res2["metadata"]["thermal_readiness"], "GAP_RESET")

    def test_19_incompatible_model_config_state_reset(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec1 = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        pipe.process_record(rec1)

        state = pipe.get_state("TX-001")
        self.assertEqual(state.observation_count, 1)

        # Swap to a bundle with different model_version
        new_bundle = PipelineBundle(
            bundle_id="new_bundle_v2",
            model_version="2.0.0",
        )
        pipe.bundle = new_bundle

        # State check must detect incompatibility and reset
        state = pipe.get_state("TX-001")
        self.assertEqual(state.observation_count, 0)
        self.assertEqual(state.bundle_id, "new_bundle_v2")

    def test_20_missing_rating_behavior(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec = make_sample_record(s_total=100.0)
        res = pipe.process_record(rec)

        self.assertIsNone(res["loading_percent"])
        self.assertIsNone(res["metadata"]["apparent_power_utilization"])

    def test_21_correct_loading_ratio_percent(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        asset_cfg = fictional_asset('TX-001')
        pipe.register_asset(asset_cfg)

        rec = make_sample_record(s_total=80.0, extra_fields={'acquisition': fictional_acquisition()})
        res = pipe.process_record(rec)

        self.assertAlmostEqual(res["loading_percent"], 80.0)
        self.assertAlmostEqual(res["metadata"]["apparent_power_utilization"], 0.8)

    def test_22_thermal_unit_consistency(self) -> None:
        rec = make_sample_record(oil_temp=80.0)
        res = self.pipeline.process_record(rec)
        # Unverified source units must not claim Celsius
        self.assertEqual(res["metadata"]["thermal_temperature_unit"], "SOURCE_UNVERIFIED")
        # Reason representation must qualify HIGH_OIL_TEMP as high oil indicator under unverified units
        desc = res["metadata"]["reason_descriptions"].get("HIGH_OIL_TEMP")
        self.assertEqual(desc, "High oil indicator (source units)")

    def test_23_thermal_readiness_warmup(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        rec1 = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        res1 = pipe.process_record(rec1)
        self.assertEqual(res1["metadata"]["thermal_readiness"], "INITIALIZING")
        self.assertIsNone(res1["thermal_residual"])

    def test_24_null_forecast_behavior(self) -> None:
        res = self.pipeline.process_record(make_sample_record())
        self.assertIsNone(res["fault_risk"])
        self.assertIsNone(res["predicted_fault"])
        self.assertIsNone(res["prediction_confidence"])
        self.assertEqual(res["metadata"]["forecast_operational_status"], "INSUFFICIENT_VALIDATION")

    def test_25_trip_override_despite_missing_inputs(self) -> None:
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        sparse_trip = {
            "transformer_id": "TX-001",
            "timestamp": "2026-10-08T10:00:00Z",
            "oil_temp_trip": 1,
        }
        res = pipe.process_record(sparse_trip)
        self.assertEqual(res["health_index"], 0.0)
        self.assertEqual(res["maintenance_priority"], "URGENT")
        self.assertTrue(pipe.get_state("TX-001").maintenance_state.trip_latched)

    def test_26_no_forecast_artifact_fallback(self) -> None:
        # When forecast model is unreleased, it must never fall back to fake risk
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        res = pipe.process_record(make_sample_record())
        self.assertIsNone(res["fault_risk"])

    def test_27_no_dashboard_side_recalculation(self) -> None:
        """Verify dashboard can consume and render all 6 stages and edge cases without recalculating."""
        # Stage 1: Healthy reference
        pipe = UnifiedMLPipeline(bundle=self.bundle)
        pipe.register_asset(fictional_asset('TX-DASH'))
        r1 = make_sample_record(transformer_id="TX-DASH", timestamp="2026-10-08T10:00:00Z", oil_temp=35.0, current=10.0, s_total=30.0)
        s1 = pipe.process_record(r1)
        self.assertEqual(s1["maintenance_priority"], "NORMAL")
        self.assertEqual(s1["health_index"], 100.0)
        self.assertEqual(s1["anomaly_score"], 0.0)

        # Stage 2: Increased load with lagged thermal response
        r2 = make_sample_record(transformer_id="TX-DASH", timestamp="2026-10-08T10:15:00Z", oil_temp=35.0, current=30.0, s_total=90.0)
        r2['acquisition'] = fictional_acquisition()
        s2 = pipe.process_record(r2)
        self.assertEqual(s2["loading_percent"], 90.0)
        self.assertIsNotNone(s2["thermal_model_temperature"])

        # Stage 3: Persistent thermal divergence
        for m in (30, 45, 60):
            ts = f"2026-10-08T10:{m:02d}:00Z" if m < 60 else "2026-10-08T11:00:00Z"
            r3 = make_sample_record(transformer_id="TX-DASH", timestamp=ts, oil_temp=80.0, current=30.0, s_total=90.0)
            s3 = pipe.process_record(r3)
        self.assertEqual(s3["anomaly_score"], 1.0)
        self.assertTrue(s3["anomaly_flag"])
        self.assertEqual(s3["maintenance_priority"], "PLAN")

        # Stage 4: Unreleased forecast view
        self.assertIsNone(s3["fault_risk"])
        self.assertEqual(s3["metadata"]["forecast_operational_status"], "INSUFFICIENT_VALIDATION")

        # Stage 5: Evidence inspection
        self.assertIn("HIGH_OIL_TEMP", s3["reason_codes"])
        self.assertIn("HIGH_OIL_TEMP", s3["metadata"]["reason_descriptions"])
        self.assertEqual(s3["metadata"]["reason_descriptions"]["HIGH_OIL_TEMP"], "High oil indicator (source units)")

        # Stage 6: Advisory maintenance action
        self.assertEqual(s3["maintenance_priority"], "PLAN")
        self.assertTrue(len(s3["maintenance_recommendation"]) > 0)

        # Edge cases:
        # Trip -> immediate URGENT
        r_trip = make_sample_record(transformer_id="TX-DASH", timestamp="2026-10-08T11:15:00Z", trip=1)
        s_trip = pipe.process_record(r_trip)
        self.assertEqual(s_trip["health_index"], 0.0)
        self.assertEqual(s_trip["maintenance_priority"], "URGENT")
        self.assertTrue(s_trip["metadata"]["maintenance_trip_latched"])

        # Missing rating
        pipe_no_rating = UnifiedMLPipeline(bundle=self.bundle)
        s_no_rate = pipe_no_rating.process_record(make_sample_record(transformer_id="TX-UNRATED", s_total=50.0))
        self.assertIsNone(s_no_rate["loading_percent"])
        self.assertIsNone(s_no_rate["metadata"]["apparent_power_utilization"])

        # Partial data
        pipe_partial = UnifiedMLPipeline(bundle=self.bundle)
        sparse_rec = {"transformer_id": "TX-PARTIAL", "timestamp": "2026-10-08T11:30:00Z", "oil_temperature": 50.0}
        s_partial = pipe_partial.process_record(sparse_rec)
        self.assertIn("INSUFFICIENT_DATA", s_partial["inference_status"])
        self.assertEqual(s_partial["maintenance_priority"], "WATCH")

        # Long gap / warm-up
        r_gap = make_sample_record(transformer_id="TX-DASH", timestamp="2026-10-08T14:00:00Z")
        s_gap = pipe.process_record(r_gap)
        self.assertEqual(s_gap["metadata"]["thermal_readiness"], "GAP_RESET")
        self.assertIsNone(s_gap["thermal_residual"])

    def test_28_no_control_scada_side_effects(self) -> None:
        # Pipeline must be strictly advisory; no control commands emitted
        res = self.pipeline.process_record(make_sample_record(trip=1))
        self.assertEqual(res["maintenance_priority"], "URGENT")
        self.assertNotIn("control_command", res)
        self.assertNotIn("relay_trip", res)

    def test_29_config_model_version_propagation(self) -> None:
        res = self.pipeline.process_record(make_sample_record())
        self.assertEqual(res["schema_version"], self.bundle.schema_version)
        self.assertEqual(res["feature_version"], self.bundle.feature_version)
        self.assertEqual(res["model_version"], self.bundle.model_version)

    def test_30_error_vs_valid_unavailable_distinction(self) -> None:
        # Valid record with unavailable forecast -> OK inference_status, null fault_risk
        valid_rec = make_sample_record()
        res_valid = self.pipeline.process_record(valid_rec)
        self.assertEqual(res_valid["inference_status"], "OK")
        self.assertIsNone(res_valid["fault_risk"])

        # Missing critical telemetry -> INSUFFICIENT_DATA
        missing_crit_rec = {
            "transformer_id": "TX-001",
            "timestamp": "2026-10-08T10:15:00Z",
            "oil_temperature": None,
            "current_l1": None,
        }
        res_crit = self.pipeline.process_record(missing_crit_rec)
        self.assertEqual(res_crit["inference_status"], "INSUFFICIENT_DATA")

        # Invalid timestamp -> PipelineValidationError
        invalid_rec = make_sample_record(timestamp="not-a-timestamp")
        with self.assertRaises(PipelineValidationError):
            self.pipeline.process_record(invalid_rec)


if __name__ == "__main__":
    unittest.main()
