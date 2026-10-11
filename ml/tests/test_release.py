"""Phase 08 — Model Metadata and Release Validation Test Suite.

Verifies:
1. Manifest completeness
2. Artifact hash consistency
3. Exact feature order
4. Schema compatibility
5. Feature compatibility
6. Preprocessing/model compatibility
7. Configuration compatibility
8. State compatibility
9. Rollback/reset behavior
10. Unit consistency
11. Threshold provenance
12. HI weight consistency
13. Persistence configuration
14. Null forecast serialization
15. Null loading without rating
16. Thermal unready serialization
17. Excluded-field absence (VL12, VL23, VL31)
18. WTI exclusion from continuous temperature
19. No target-derived predictor presence
20. RUL unavailable status
21. Historical/synthetic provenance separation
22. Deterministic versioned replay
23. Final unified contract compatibility
24. Backend/API compatibility
25. Dashboard consumption compatibility
26. Demo/runbook reproducibility checks
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import pandas as pd

from ml.features.feature_engineering import REQUIRED_TELEMETRY_COLUMNS
from ml.pipeline.asset_config import AssetConfig
from ml.pipeline.bundle import PipelineBundle
from ml.pipeline.manifest import load_release_manifest, ReleaseManifest
from ml.pipeline.orchestrator import UnifiedMLPipeline, analyze
from ml.tests.test_pipeline import make_sample_record


class TestPhase08ModelMetadataAndRelease(unittest.TestCase):
    """Rigorous Phase 08 release candidate validation."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.manifest = load_release_manifest()
        self.bundle = PipelineBundle.load_from_processed_dir()
        self.pipeline = UnifiedMLPipeline(bundle=self.bundle)
        self.asset_cfg = AssetConfig(transformer_id="TX-001", rated_power_kva=100.0)
        self.pipeline.register_asset(self.asset_cfg)

    def test_01_manifest_completeness(self) -> None:
        """Verify release manifest contains all mandatory sections and versions."""
        self.assertEqual(self.manifest.manifest_version, "1.0.0")
        self.assertEqual(self.manifest.release_candidate_status, "CANDIDATE_REVIEWABLE")
        self.assertEqual(self.manifest.operational_release_status, "CAPABILITY_LIMITED")

        expected_versions = {
            "schema_version",
            "feature_version",
            "preprocessing_version",
            "model_version",
            "thermal_parameter_version",
            "anomaly_detector_version",
            "prediction_model_version",
            "training_dataset_version",
            "bundle_version",
        }
        for v in expected_versions:
            self.assertIn(v, self.manifest.versions)
            self.assertEqual(self.manifest.versions[v], "1.0.0")

    def test_02_artifact_hash_consistency(self) -> None:
        """Verify all declared SHA-256 hashes match actual files on disk."""
        results = self.manifest.verify_artifact_hashes(self.repo_root)
        self.assertTrue(len(results) > 0)
        for path_name, is_valid in results.items():
            self.assertTrue(is_valid, f"Hash verification failed for: {path_name}")

    def test_03_exact_feature_order(self) -> None:
        """Verify exact frozen feature order in prediction artifact and manifest."""
        expected_order = [
            "oil_temperature",
            "ambient_temperature",
            "temperature_slope",
            "current_mean",
            "current_imbalance_pct",
            "apparent_power_total",
            "rolling_load_mean",
            "thermal_residual",
        ]
        manifest_order = self.manifest.subsystem_metadata["proxy_prediction"]["feature_order"]
        self.assertEqual(manifest_order, expected_order)

        # Cross-check with disk artifact
        pred_file = self.repo_root / "data" / "processed" / "proxy_prediction_params.json"
        with open(pred_file, "r", encoding="utf-8") as f:
            pred_data = json.load(f)
        disk_order = pred_data["primary_experiment"]["features"]["order"]
        self.assertEqual(disk_order, expected_order)

    def test_04_schema_compatibility(self) -> None:
        """Verify schema version conforms to semantic version 1.0.0 across pipeline."""
        self.assertEqual(self.bundle.schema_version, "1.0.0")
        sample = make_sample_record()
        res = self.pipeline.process_record(sample)
        self.assertEqual(res["schema_version"], "1.0.0")

    def test_05_feature_compatibility(self) -> None:
        """Verify feature version conforms to 1.0.0 across pipeline output."""
        self.assertEqual(self.bundle.feature_version, "1.0.0")
        sample = make_sample_record()
        res = self.pipeline.process_record(sample)
        self.assertEqual(res["feature_version"], "1.0.0")

    def test_06_preprocessing_model_compatibility(self) -> None:
        """Verify preprocessor artifact matches prediction feature dimension."""
        pred_file = self.repo_root / "data" / "processed" / "proxy_prediction_params.json"
        with open(pred_file, "r", encoding="utf-8") as f:
            pred_data = json.load(f)
        preproc = pred_data["preprocessing"]
        means = preproc["means"]
        scales = preproc["scales"]
        feat_names = preproc["feature_names"]

        self.assertEqual(len(means), len(feat_names))
        self.assertEqual(len(scales), len(feat_names))
        for col in feat_names:
            self.assertIn(col, means)
            self.assertIn(col, scales)

    def test_07_configuration_compatibility(self) -> None:
        """Verify bundle configurations load with consistent thermal and anomaly settings."""
        self.assertEqual(self.bundle.thermal_config.continuity_gap_hours, 0.5)
        self.assertEqual(self.bundle.anomaly_config.a_on, 0.5)
        self.assertEqual(self.bundle.anomaly_config.min_persistence_observations, 3)

    def test_08_state_compatibility(self) -> None:
        """Verify state compatibility checker accepts current version and rejects incompatible."""
        self.assertTrue(self.manifest.is_state_compatible("1.0.0"))
        self.assertFalse(self.manifest.is_state_compatible("0.9.0"))
        self.assertFalse(self.manifest.is_state_compatible("2.0.0"))

    def test_09_rollback_reset_behavior(self) -> None:
        """Analytical reset restarts warm-up without erasing accepted protection/identity."""
        state = self.pipeline.get_state("TX-001")
        rec = make_sample_record(timestamp="2026-10-08T10:00:00Z", trip=1)
        self.pipeline.process_record(rec)
        self.assertIsNotNone(state.last_processed_timestamp)

        # Reset state
        self.pipeline.reset_state("TX-001")
        fresh_state = self.pipeline.get_state("TX-001")
        self.assertEqual(fresh_state.last_processed_timestamp, pd.Timestamp(rec['timestamp']))
        self.assertEqual(len(fresh_state.history_records), 1)
        self.assertFalse(fresh_state.thermal_state.is_initialized)
        self.assertEqual(fresh_state.lifecycle_status, 'REINITIALIZED')
        self.assertTrue(fresh_state.maintenance_state.trip_latched)
        changed = dict(rec, oil_temp_trip=0)
        self.assertEqual(self.pipeline.process_record(changed)['ingestion_outcome'], 'CONFLICT')
        next_record = make_sample_record(timestamp='2026-10-08T10:05:00Z', trip=0)
        result = self.pipeline.process_record(next_record)
        self.assertEqual(result['metadata']['thermal_readiness'], 'INITIALIZING')
        self.assertEqual(result['health_index'], 0)
        self.assertTrue(result['metadata']['maintenance_trip_latched'])

    def test_10_unit_consistency(self) -> None:
        """Verify thermal units are labeled SOURCE_UNVERIFIED and physical limit is not claimed."""
        self.assertEqual(self.bundle.thermal_config.temperature_unit, "SOURCE_UNVERIFIED")
        res = self.pipeline.process_record(make_sample_record())
        self.assertEqual(res["metadata"]["thermal_temperature_unit"], "SOURCE_UNVERIFIED")

    def test_11_threshold_provenance(self) -> None:
        """Verify all anomaly thresholds have documented provenance."""
        for name, sig_thresh in self.bundle.anomaly_config.thresholds.items():
            self.assertIn("TRAIN_REF", sig_thresh.provenance)
            self.assertIn(sig_thresh.direction, ("upper", "lower"))

    def test_12_hi_weight_consistency(self) -> None:
        """Verify Health Index weights sum exactly to 1.0 with correct pillar weights."""
        weights = self.manifest.subsystem_metadata["health_index"]["weights"]
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=7)
        self.assertEqual(weights["thermal"], 0.30)
        self.assertEqual(weights["electrical"], 0.20)
        self.assertEqual(weights["loading"], 0.10)
        self.assertEqual(weights["oil"], 0.15)
        self.assertEqual(weights["protection"], 0.20)
        self.assertEqual(weights["anomaly"], 0.05)

    def test_13_persistence_configuration(self) -> None:
        """Verify persistence configuration requires at least 3 readings and 30 minutes."""
        cfg = self.bundle.anomaly_config
        self.assertGreaterEqual(cfg.min_persistence_observations, 3)
        self.assertGreaterEqual(cfg.min_persistence_span_hours, 0.5)

    def test_14_null_forecast_serialization(self) -> None:
        """Verify forecast fields are serialized as None with INSUFFICIENT_VALIDATION status."""
        res = self.pipeline.process_record(make_sample_record())
        self.assertIsNone(res["fault_risk"])
        self.assertIsNone(res["predicted_fault"])
        self.assertIsNone(res["prediction_confidence"])
        self.assertEqual(res["metadata"]["forecast_operational_status"], "INSUFFICIENT_VALIDATION")

    def test_15_null_loading_without_rating(self) -> None:
        """Verify loading percent and utilization are null when rating is unverified."""
        pipe_unrated = UnifiedMLPipeline(bundle=self.bundle)
        rec = make_sample_record(transformer_id="TX-UNRATED", s_total=50.0)
        res = pipe_unrated.process_record(rec)
        self.assertIsNone(res["loading_percent"])
        self.assertIsNone(res["metadata"]["apparent_power_utilization"])

    def test_16_thermal_unready_serialization(self) -> None:
        """Verify initial observation produces INITIALIZING readiness and suppressed residual."""
        pipe_fresh = UnifiedMLPipeline(bundle=self.bundle)
        pipe_fresh.register_asset(self.asset_cfg)
        res = pipe_fresh.process_record(make_sample_record())
        self.assertEqual(res["metadata"]["thermal_readiness"], "INITIALIZING")
        self.assertIsNone(res["thermal_residual"])

    def test_17_excluded_field_absence(self) -> None:
        """Verify excluded raw fields (VL12, VL23, VL31) are absent from canonical schema."""
        for field in ("VL12", "VL23", "VL31"):
            self.assertNotIn(field, REQUIRED_TELEMETRY_COLUMNS)

    def test_18_wti_exclusion(self) -> None:
        """Verify winding temperature indicator is excluded from continuous thermal features."""
        from ml.features.feature_engineering import FEATURE_COLUMNS
        self.assertNotIn("winding_temperature", FEATURE_COLUMNS)
        self.assertNotIn("winding_temperature_level", FEATURE_COLUMNS)

    def test_19_no_target_derived_predictor_presence(self) -> None:
        """Verify forecast feature list contains no target-derived or lookahead features."""
        manifest_order = self.manifest.subsystem_metadata["proxy_prediction"]["feature_order"]
        for feat in manifest_order:
            self.assertNotIn("alarm", feat)
            self.assertNotIn("trip", feat)
            self.assertNotIn("target", feat)
            self.assertNotIn("onset", feat)

    def test_20_rul_unavailable_status(self) -> None:
        """Verify RUL status is explicitly recorded as NOT ESTIMABLE / ORGANIZER CONFIRMATION REQUIRED."""
        rul_status = self.manifest.rul_status["status"]
        self.assertEqual(rul_status, "NOT ESTIMABLE / ORGANIZER CONFIRMATION REQUIRED")

    def test_21_historical_synthetic_provenance_separation(self) -> None:
        """Verify manifest explicitly separates historical evaluation from synthetic demonstration."""
        sep = self.manifest.synthetic_vs_historical_separation
        self.assertIn("historical_data", sep)
        self.assertIn("synthetic_data", sep)
        self.assertIn("cross_contamination_policy", sep)

    def test_22_deterministic_versioned_replay(self) -> None:
        """Verify replay of identical input records produces bit-for-bit identical results."""
        pipe1 = UnifiedMLPipeline(bundle=self.bundle)
        pipe2 = UnifiedMLPipeline(bundle=self.bundle)
        pipe1.register_asset(self.asset_cfg)
        pipe2.register_asset(self.asset_cfg)

        rec = make_sample_record(timestamp="2026-10-08T10:00:00Z")
        res1 = pipe1.process_record(rec)
        res2 = pipe2.process_record(rec)

        self.assertEqual(res1["health_index"], res2["health_index"])
        self.assertEqual(res1["anomaly_score"], res2["anomaly_score"])
        self.assertEqual(res1["maintenance_priority"], res2["maintenance_priority"])

    def test_23_final_unified_contract_compatibility(self) -> None:
        """Verify unified result contains all 22 required contract fields."""
        res = self.pipeline.process_record(make_sample_record())
        required_keys = {
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
        }
        for k in required_keys:
            self.assertIn(k, res)

    def test_24_backend_api_compatibility(self) -> None:
        """Verify analyze() public functional entrypoint matches backend contract."""
        tx_dict = {"id": "TX-001", "name": "TX-001", "rated_power_kva": 100.0}
        rec = make_sample_record()
        res = analyze(transformer=tx_dict, record=rec, history=[])
        self.assertIsInstance(res, dict)
        self.assertEqual(res["transformer_id"], "TX-001")
        self.assertIn("health_index", res)
        self.assertIn("maintenance_priority", res)

    def test_25_dashboard_consumption_compatibility(self) -> None:
        """Verify metadata fields consumed by frontend components exist and are populated."""
        res = self.pipeline.process_record(make_sample_record())
        self.assertIn("metadata", res)
        meta = res["metadata"]
        self.assertIn("thermal_readiness", meta)
        self.assertIn("forecast_operational_status", meta)
        self.assertIn("reason_descriptions", meta)
        self.assertIn("coverage_overall", meta)

    def test_26_demo_runbook_reproducibility_checks(self) -> None:
        """Verify capability matrix covers all 11 core system capabilities."""
        caps = self.manifest.capability_matrix
        self.assertEqual(len(caps), 11)
        self.assertEqual(caps["unified_ml_pipeline"], "AVAILABLE / VERIFIED")
        self.assertEqual(caps["remaining_useful_life_rul"], "NOT ESTIMABLE / ORGANIZER CONFIRMATION REQUIRED")
        self.assertEqual(caps["operational_fault_probability"], "INSUFFICIENT_VALIDATION (gated to null; single-class validation partition)")


if __name__ == "__main__":
    unittest.main()
