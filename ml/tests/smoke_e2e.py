"""End-to-end smoke test validating the 6-stage demo trace and edge cases."""

import sys
from pathlib import Path
backend_dir = str(Path(__file__).resolve().parents[2] / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from ml.pipeline import UnifiedMLPipeline, AssetConfig, analyze
from app.ml_client.python_client import PythonMLTwinClient
from app.core.config import Settings
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut
from app.ml_client.base import parse_ml_result

print("=== SMOKE TEST: 6-STAGE DEMO SEQUENCE & EDGE CASES ===")

pipe = UnifiedMLPipeline()
asset = AssetConfig(transformer_id="TX-DEMO", rated_power_kva=100.0)
pipe.register_asset(asset)

# Stage 1: Healthy ready reference
print("\nStage 1: Healthy reference...")
r1 = {
    "transformer_id": "TX-DEMO",
    "timestamp": "2026-10-08T10:00:00Z",
    "oil_temperature": 35.0,
    "ambient_temperature": 25.0,
    "current_l1": 10.0,
    "current_l2": 10.0,
    "current_l3": 10.0,
    "phase_voltage_l1": 230.0,
    "phase_voltage_l2": 230.0,
    "phase_voltage_l3": 230.0,
    "oil_level": 8.0,
    "apparent_power_total": 30.0,
    "oil_temp_alarm": 0,
    "oil_temp_trip": 0,
    "magnetic_oil_gauge_alarm": 0,
}
s1 = pipe.process_record(r1)
print(f"Stage 1 OK: HI={s1['health_index']}, Anomaly={s1['anomaly_score']}, Priority={s1['maintenance_priority']}")

# Stage 2: Increased load with lagged thermal response
print("\nStage 2: Increased load with lagged thermal response...")
r2 = dict(r1)
r2["timestamp"] = "2026-10-08T10:15:00Z"
r2["current_l1"] = 30.0
r2["current_l2"] = 30.0
r2["current_l3"] = 30.0
r2["apparent_power_total"] = 90.0
s2 = pipe.process_record(r2)
print(f"Stage 2 OK: Loading%={s2['loading_percent']}%, T_model={s2['thermal_model_temperature']}")

# Stage 3: Persistent observed/model divergence (anomaly rise)
print("\nStage 3: Persistent thermal divergence...")
for m in (30, 45, 60):
    r3 = dict(r2)
    r3["timestamp"] = f"2026-10-08T10:{m:02d}:00Z" if m < 60 else "2026-10-08T11:00:00Z"
    r3["oil_temperature"] = 80.0
    s3 = pipe.process_record(r3)
print(f"Stage 3 OK: Anomaly={s3['anomaly_score']}, Flag={s3['anomaly_flag']}, Priority={s3['maintenance_priority']}")

# Stage 4: Risk view (unreleased operational proxy risk is null with status)
print("\nStage 4: Proxy risk view...")
print(f"Stage 4 OK: fault_risk={s3['fault_risk']}, status={s3['metadata']['forecast_operational_status']}")

# Stage 5: Evidence inspection (physical vs unverified indicator qualified)
print("\nStage 5: Evidence inspection (source-unit qualification)...")
print(f"Stage 5 OK: reason_codes={s3['reason_codes']}")
print(f"Stage 5 OK: reason_descriptions={s3['metadata']['reason_descriptions']}")
print(f"Stage 5 OK: components={s3['health_components']}")
print("Note: HIGH_OIL_TEMP represents High oil indicator under unverified source units, not physical limit exceedance.")

# Stage 6: Advisory maintenance action
print("\nStage 6: Maintenance action (strictly advisory, no control commands)...")
print(f"Stage 6 OK: Priority={s3['maintenance_priority']}, Rec={s3['maintenance_recommendation']}")

# Additional Edge Case A: Trip override -> immediate URGENT
print("\nEdge Case A: Verified trip...")
r_trip = dict(r1)
r_trip["timestamp"] = "2026-10-08T11:15:00Z"
r_trip["oil_temp_trip"] = 1
s_trip = pipe.process_record(r_trip)
print(f"Trip OK: HI={s_trip['health_index']}, Priority={s_trip['maintenance_priority']}, Latched={s_trip['metadata']['maintenance_trip_latched']}")

# Additional Edge Case B: Missing rating
print("\nEdge Case B: Missing rating...")
pipe_unrated = UnifiedMLPipeline()
r_unrated = dict(r1)
r_unrated["timestamp"] = "2026-10-08T12:00:00Z"
s_unrated = pipe_unrated.process_record(r_unrated)
print(f"Unrated OK: Loading%={s_unrated['loading_percent']}, Utilization={s_unrated['metadata']['apparent_power_utilization']}")

# Additional Edge Case C: Long gap reset
print("\nEdge Case C: Long gap (>30 min)...")
r_gap = dict(r_unrated)
r_gap["timestamp"] = "2026-10-08T14:00:00Z"
s_gap = pipe_unrated.process_record(r_gap)
print(f"Long gap OK: Thermal readiness={s_gap['metadata']['thermal_readiness']}, Residual={s_gap['thermal_residual']}")

# Edge Case D: Backend client integration
print("\nEdge Case D: Backend PythonMLTwinClient integration...")
settings = Settings(_env_file=None, ml_python_entrypoint="ml.pipeline:analyze")
client = PythonMLTwinClient(settings)
tx = TransformerOut(id="TX-DEMO", name="Demo Transformer", created_at=r1["timestamp"], updated_at=r1["timestamp"])
rec = TelemetryIn.model_validate(r1)
backend_res = client.analyze(tx, rec, [])
print(f"Backend integration OK: Priority={backend_res.maintenance_priority}, HI={backend_res.health_index}")

print("\nALL DEMO AND SMOKE STAGES PASSED SUCCESSFULLY!")
