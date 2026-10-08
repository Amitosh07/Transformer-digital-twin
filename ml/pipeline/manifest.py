"""Release manifest loader and integrity validator for the ML / Digital Twin layer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


DEFAULT_MANIFEST_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "release_manifest.json"
)


@dataclass(frozen=True)
class ReleaseManifest:
    """Strongly-typed release manifest representation."""

    manifest_id: str
    manifest_version: str
    created_at: str
    release_candidate_status: str
    operational_release_status: str
    versions: Mapping[str, str]
    provenance_hashes: Mapping[str, Any]
    dataset_accounting: Mapping[str, Any]
    subsystem_metadata: Mapping[str, Any]
    loading_and_nameplate: Mapping[str, Any]
    rul_status: Mapping[str, Any]
    standards_provenance: Mapping[str, Any]
    state_compatibility_and_rollback: Mapping[str, Any]
    synthetic_vs_historical_separation: Mapping[str, Any]
    organizer_clarifications_and_future_revalidation: Mapping[str, Any]
    capability_matrix: Mapping[str, str]
    release_safety_declarations: list[str]

    @classmethod
    def load(cls, path: Path | str | None = None) -> ReleaseManifest:
        """Load manifest from json file."""
        if path is None:
            path = DEFAULT_MANIFEST_PATH
        else:
            path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            manifest_id=str(data["manifest_id"]),
            manifest_version=str(data["manifest_version"]),
            created_at=str(data["created_at"]),
            release_candidate_status=str(data["release_candidate_status"]),
            operational_release_status=str(data["operational_release_status"]),
            versions=data.get("versions", {}),
            provenance_hashes=data.get("provenance_hashes", {}),
            dataset_accounting=data.get("dataset_accounting", {}),
            subsystem_metadata=data.get("subsystem_metadata", {}),
            loading_and_nameplate=data.get("loading_and_nameplate", {}),
            rul_status=data.get("rul_status", {}),
            standards_provenance=data.get("standards_provenance", {}),
            state_compatibility_and_rollback=data.get("state_compatibility_and_rollback", {}),
            synthetic_vs_historical_separation=data.get("synthetic_vs_historical_separation", {}),
            organizer_clarifications_and_future_revalidation=data.get(
                "organizer_clarifications_and_future_revalidation", {}
            ),
            capability_matrix=data.get("capability_matrix", {}),
            release_safety_declarations=list(data.get("release_safety_declarations", [])),
        )

    def verify_artifact_hashes(self, repo_root: Path | str | None = None) -> dict[str, bool]:
        """Verify that files on disk match their declared SHA-256 hashes in the manifest."""
        if repo_root is None:
            repo_root = Path(__file__).resolve().parents[2]
        else:
            repo_root = Path(repo_root)

        results = {}

        # Check raw sources
        raw_hashes = self.provenance_hashes.get("raw_sources", {})
        raw_dir = repo_root / "data" / "raw"
        for fname, expected_hash in raw_hashes.items():
            fpath = raw_dir / fname
            if fpath.exists():
                actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
                results[f"raw/{fname}"] = (actual_hash == expected_hash)
            else:
                results[f"raw/{fname}"] = False

        # Check processed artifacts
        proc_hashes = self.provenance_hashes.get("processed_artifacts", {})
        proc_dir = repo_root / "data" / "processed"
        for fname, expected_hash in proc_hashes.items():
            fpath = proc_dir / fname
            if fpath.exists():
                actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
                results[f"processed/{fname}"] = (actual_hash == expected_hash)
            else:
                results[f"processed/{fname}"] = False

        return results

    def is_state_compatible(self, version: str) -> bool:
        """Check if an existing persisted state version is compatible with this release."""
        compat_versions = self.state_compatibility_and_rollback.get("compatible_state_versions", [])
        return version in compat_versions


def load_release_manifest(path: Path | str | None = None) -> ReleaseManifest:
    """Convenience accessor for loading the release manifest."""
    return ReleaseManifest.load(path)
