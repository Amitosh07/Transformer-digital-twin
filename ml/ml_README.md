# Machine Learning & Digital Twin Intelligence Layer

**Owner:** Person 1 — ML + Digital Twin / Team Lead  
**Release Version:** `v1.0.0` (Release Candidate)  
**Status:** Completed Phases 00–08  
**Authoritative Specifications:** `dataschema.md` v1.0.0, `mlcontract.md` v1.0.0, `docs/methodology.md` v1.0.0, `docs/model_card.md` v1.0.0, `data/processed/release_manifest.json`  

---

## 1. Mission & Overview

The ML/Twin layer transforms multivariate canonical transformer telemetry into:
1. **Dynamic Thermodynamic Twin Tracking:** Continuous first-order ODE tracking expected top-oil temperature and generating signed physical residuals.
2. **Multivariate Anomaly Detection:** Hybrid statistical quantile reference ($Q_{0.95}/Q_{0.995}$) and engineering protection violation severity with temporal persistence.
3. **6-Pillar Composite Health Index:** Instantaneous operational condition score ($0$ to $100$) integrating thermal, electrical, loading, oil, protection, and anomaly pillars.
4. **Prescriptive Advisory Maintenance Engine:** Actionable maintenance priority (`NORMAL`, `WATCH`, `PLAN`, `URGENT`) and clear natural-language recommendations without autonomous control commands.
5. **Experimental Proxy Forecast Classifier:** Next-hour proxy abnormal onset prediction, gated to `null` operationally due to single-class validation limits.

---

## 2. Architecture & Entrypoint

The primary operational entrypoint is `analyze()` or `UnifiedMLPipeline`, providing an idempotent, stateful, multi-asset isolated inference boundary:

```python
from ml.pipeline import UnifiedMLPipeline, AssetConfig, analyze

# Option A: Functional entrypoint (Backend PythonMLTwinClient contract)
result = analyze(
    record={
        "transformer_id": "TX-001",
        "timestamp": "2026-10-09T10:00:00Z",
        "oil_temperature": 45.0,
        "ambient_temperature": 25.0,
        "current_l1": 15.0,
        "current_l2": 15.0,
        "current_l3": 15.0,
        "phase_voltage_l1": 230.0,
        "phase_voltage_l2": 230.0,
        "phase_voltage_l3": 230.0,
        "oil_level": 8.0,
        "apparent_power_total": 50.0,
        "oil_temp_alarm": 0,
        "oil_temp_trip": 0,
        "magnetic_oil_gauge_alarm": 0,
    },
    asset_config=AssetConfig(transformer_id="TX-001", rated_power_kva=100.0)
)

print(result["health_index"])           # 100.0
print(result["maintenance_priority"])   # NORMAL
print(result["fault_risk"])             # None (Gated: INSUFFICIENT_VALIDATION)
```

---

## 3. Directory Layout

```
ml/
├── adaptors/                  # Source CSV to canonical telemetry conversion
├── anomaly/                   # Phase 02 hybrid quantile anomaly detector
├── evaluation/                # Phase 06 chronological time-aware evaluation engine
├── features/                  # Phase 00 causal feature engineering (no look-ahead)
├── health/                    # Phase 03 6-pillar composite Health Index engine
├── maintenance/               # Phase 05 advisory prescriptive maintenance engine
├── pipeline/                  # Phase 07/08 unified orchestrator, bundle & manifest
│   ├── asset_config.py        # Verified asset nameplate configuration dataclass
│   ├── bundle.py              # PipelineBundle parameter container
│   ├── manifest.py            # Phase 08 ReleaseManifest and integrity validator
│   ├── orchestrator.py        # UnifiedMLPipeline stateful orchestrator & analyze()
│   └── state.py               # AssetPipelineState isolated per-asset container
├── prediction/                # Phase 04 next-hour proxy onset prediction model
├── tests/                     # Unit test suite & end-to-end smoke tests
├── thermal/                   # Phase 01 first-order thermodynamic ODE twin
└── ml_README.md               # This document
```

---

## 4. Contract Conformance & Gating Rules

The pipeline strictly guarantees the following invariants:

| Condition | Pipeline Output Behavior | Rationale |
|---|---|---|
| **Missing nameplate rating** | `loading_percent = null`, `apparent_power_utilization = null` | Prevents guessing fictitious rated capacity. |
| **Operational proxy risk** | `fault_risk = null`, `predicted_fault = null`, `prediction_confidence = null` | Primary validation split has 0 positive onsets; calibration cannot be verified. |
| **Initial warm-up period** | `thermal_residual = null`, `thermal_readiness = "INITIALIZING"` | Requires 3 valid readings spanning $\ge 30$ min before activating residual. |
| **Telemetry gap $> 30$ min** | `thermal_readiness = "GAP_RESET"`, residual suppressed | Linear continuity invalid across gaps; state is reset. |
| **Active/latched trip contact** | `health_index = 0.0`, `maintenance_priority = "URGENT"` | Protection trip contact hard overrides all other sub-indices. |
| **RUL estimation** | `RUL = NOT ESTIMABLE / ORGANIZER CONFIRMATION REQUIRED` | RUL is not implemented or estimated; lifetime is never fabricated. |
| **Autonomous control** | Zero control commands emitted | System is strictly advisory for human operators. |

---

## 5. Parameter Artifacts & Hashes

Fitted parameter artifacts live in `data/processed/` with cryptographic SHA-256 fingerprints recorded in `release_manifest.json`:

| File | Size | SHA-256 Hash |
|---|---|---|
| `canonical_telemetry.csv` | 2,734,991 B | `a5469bb12c83aec3565adb89f4fd2ad54274443351d26a263301b9b06de1ef63` |
| `quality_report.json` | 1,742 B | `c1b44353c254c38376894b7f65f8cb3da9cdb2db90eb5c59b077ba6e84c83244` |
| `thermal_twin_params.json` | 2,338 B | `a6d614182313ca111a36c756f235213c714d2d46554969b0fc7be4a40c6cd741` |
| `anomaly_detector_params.json` | 4,085 B | `670b0c2063cdfa7db8455a033f56f0d34ced7da773841bdbf5951a297db65b72` |
| `proxy_prediction_params.json` | 12,593 B | `ee7c1f95f7cadad5e32bc8b0ba22fe9f7fc8e8bb3136c530a0c63d0693cf0f00` |
| `evaluation_report.json` | 27,655 B | `a18cafcb2625365c0347fe08df1e9c4d377c4a078434946b7177d170441625b9` |
| `release_manifest.json` | 9,812 B | `9d12b36de2d78493b7ec3afd7cb7ca0c9312cb6941b81d71e2b776a995606995` |

---

## 6. Testing & Validation Suite

To run all unit tests across the ML layer:

```bash
# Run all 173 ML tests across Phases 00-07
python -m unittest discover -s ml/tests -p "test_*.py"

# Run Phase 08 Release tests
python -m unittest ml/tests/test_release.py

# Run the 6-stage end-to-end smoke verification
python -m ml.tests.smoke_e2e
```

---

## 7. Future PowerNext Track 2 Revalidation

When the official competition dataset is provided by the organizers, execute the **12-Step Revalidation Protocol** documented in [`docs/methodology.md`](file:///c:/Users/Amitosh%20Nigam/Desktop/Transformer-digital-twin/docs/methodology.md) Section 9 before promoting the model to production judging.
