"""Unified ML and Digital Twin pipeline package.

Exposes:
- UnifiedMLPipeline: Deterministic stateful pipeline orchestrator
- PipelineBundle: Versioned parameters bundle for all models and engines
- AssetConfig: Verified asset nameplate configuration
- AssetPipelineState: Isolated per-asset state container
- analyze: Public entrypoint matching PythonMLTwinClient backend contract
"""

from ml.pipeline.asset_config import AssetConfig
from ml.pipeline.bundle import PipelineBundle
from ml.pipeline.manifest import ReleaseManifest, load_release_manifest
from ml.pipeline.orchestrator import (
    PipelineError,
    PipelineValidationError,
    UnifiedMLPipeline,
    analyze,
)
from ml.pipeline.state import AssetPipelineState
from ml.pipeline.session import PipelineSession, PreparedInference, CheckpointCompatibilityError, CandidateStateError

__all__ = [
    "AssetConfig",
    "AssetPipelineState",
    "PipelineBundle",
    "PipelineError",
    "PipelineValidationError",
    "ReleaseManifest",
    "UnifiedMLPipeline",
    "analyze",
    "load_release_manifest",
    "PipelineSession", "PreparedInference", "CheckpointCompatibilityError", "CandidateStateError",
]
