"""Time-Aware Evaluation package for Transformer Digital Twin (Phase 06)."""

from ml.evaluation.anomaly_eval import (
    count_flagged_episodes,
    evaluate_anomaly_on_partition,
)
from ml.evaluation.engine import (
    DEFAULT_REPORT_OUTPUT_PATH,
    EvaluationHarness,
    run_comprehensive_evaluation,
)
from ml.evaluation.fixtures_eval import (
    verify_health_index_fixtures,
    verify_maintenance_scenarios,
)
from ml.evaluation.forecast_eval import (
    evaluate_forecast_binary_partition,
    evaluate_operational_release_gate,
)
from ml.evaluation.splits import (
    DEFAULT_HORIZON_HOURS,
    DEFAULT_MAX_GAP_HOURS,
    EXPLORATORY_SPLIT_TEST_END,
    EXPLORATORY_SPLIT_TRAIN_END,
    EXPLORATORY_SPLIT_VAL_END,
    SPLIT_TRAIN_END,
    SPLIT_VAL_END,
    compute_adequately_observed_asset_days,
    compute_file_sha256,
    partition_exploratory_splits,
    partition_primary_chronological_splits,
)
from ml.evaluation.thermal_eval import (
    evaluate_thermal_twin_and_baselines,
    fit_ambient_dynamic_baseline,
    fit_ambient_offset_baseline,
)

__all__ = [
    "DEFAULT_REPORT_OUTPUT_PATH",
    "DEFAULT_HORIZON_HOURS",
    "DEFAULT_MAX_GAP_HOURS",
    "SPLIT_TRAIN_END",
    "SPLIT_VAL_END",
    "EXPLORATORY_SPLIT_TRAIN_END",
    "EXPLORATORY_SPLIT_VAL_END",
    "EXPLORATORY_SPLIT_TEST_END",
    "EvaluationHarness",
    "run_comprehensive_evaluation",
    "compute_file_sha256",
    "compute_adequately_observed_asset_days",
    "partition_primary_chronological_splits",
    "partition_exploratory_splits",
    "fit_ambient_offset_baseline",
    "fit_ambient_dynamic_baseline",
    "evaluate_thermal_twin_and_baselines",
    "count_flagged_episodes",
    "evaluate_anomaly_on_partition",
    "evaluate_forecast_binary_partition",
    "evaluate_operational_release_gate",
    "verify_health_index_fixtures",
    "verify_maintenance_scenarios",
]
