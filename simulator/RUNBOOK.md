# Transformer Digital Twin - Demo Runbook

**Owner:** Person 4 - Simulator + DevOps

---

## Quick Start

### Prerequisites
- Docker + Docker Compose installed
- Port 55433, 51885, 8001 available

### One-command startup (simulator_README section 12)

```bash
# From repository root
docker compose up --build
```

This starts: **PostgreSQL** + **MQTT Mosquitto** + **Backend** + **Simulator**

### Without Docker (development)

```bash
# Terminal 1: Start backend (see backend/README.md)
cd backend && uvicorn app.main:app --port 8000

# Terminal 2: Install simulator dependencies
cd simulator && pip install -e .

# Terminal 3: Seed data
python -m simulator.cli seed --http-url http://localhost:8000

# Terminal 4: Stream live telemetry
python -m simulator.cli stream --http-url http://localhost:8000 --interval 5
```

---

## CLI Commands

| Command | Purpose |
|---|---|
| `simulator generate` | Emit synthetic canonical records (stdout / JSON) |
| `simulator replay` | Replay historical Kaggle CSVs through the canonical adapter |
| `simulator inject` | Run a named fault scenario |
| `simulator stream` | Continuous live simulation (MQTT / HTTP) |
| `simulator demo` | Run all 5 demo scenarios in sequence |
| `simulator seed` | Bulk-seed the backend via HTTP |
| `simulator scenarios` | List available fault scenarios |
| `simulator reset` | Request a demo reset from the backend |

---

## Demo Procedure

### Step 1: Reset

```bash
python -m simulator.cli reset --http-url http://localhost:8001
```

Or run: `bash scripts/reset.sh`

### Step 2: Seed baseline data

```bash
python -m simulator.cli seed --http-url http://localhost:8001 --count 1440
```

This inserts 24 hours of normal synthetic telemetry.

### Step 3: Run demo scenarios

```bash
python -m simulator.cli demo --http-url http://localhost:8001
```

This runs 5 scenarios in sequence:

| # | Scenario | Expected Response |
|---|---|---|
| 1 | **Healthy** | Health index >= 80, anomaly score low, maintenance NORMAL |
| 2 | **Overload** | Loading > 100%, thermal stress, anomaly detected, health drops |
| 3 | **Thermal Stress** | Thermal residual rises, fault risk increases, PLAN/URGENT |
| 4 | **Current Imbalance** | Current imbalance %, neutral current rises, anomaly detected |
| 5 | **Low Oil / Alarm** | Oil level drops, MOG alarm, health drops, mentions oil |

### Step 4: Observe on Dashboard

Open the dashboard and verify:
- Health Index card shows degradation during fault scenarios
- Anomaly alerts appear
- Maintenance recommendations are generated
- Trend charts show the injected changes

### Full automated demo

```bash
bash scripts/demo.sh
```

---

## Fault Injection - Available Scenarios

| Scenario | ID | Severity | Injected Fields |
|---|---|---|---|
| HEALTHY | SCN_HEALTHY_01 | LOW | (none) |
| OVERLOAD | SCN_OVERLOAD_01 | HIGH | current_l1/l2/l3, active_power, apparent_power |
| THERMAL_STRESS | SCN_THERMAL_STRESS_01 | HIGH | oil_temperature, winding_temperature |
| RAPID_TEMPERATURE_RISE | SCN_RAPID_TEMP_RISE_01 | CRITICAL | oil_temperature, winding_temperature |
| CURRENT_IMBALANCE | SCN_CURRENT_IMBALANCE_01 | MEDIUM | current_l2, neutral_current |
| VOLTAGE_DEVIATION | SCN_VOLTAGE_DEV_01 | MEDIUM | phase_voltage_l3 |
| LOW_OIL_LEVEL | SCN_LOW_OIL_01 | HIGH | oil_level, magnetic_oil_gauge_alarm |
| ALARM_TRIP | SCN_ALARM_TRIP_01 | CRITICAL | oil_temp_alarm, oil_temp_trip, temperatures |
| SENSOR_ANOMALY | SCN_SENSOR_ANOMALY_01 | MEDIUM | oil_temperature |

### Inject a specific scenario

```bash
# Generate 10 records with overload fault
python -m simulator.cli inject --scenario OVERLOAD --count 10

# Stream with fault injection via MQTT
python -m simulator.cli stream --scenario THERMAL_STRESS --mqtt-host localhost --interval 5
```

---

## Streaming

### MQTT mode

```bash
python -m simulator.cli stream \
    --mqtt-host localhost \
    --mqtt-port 1883 \
    --interval 5 \
    --transformer-id TX-001
```

Topic: `transformer/TX-001/telemetry`

### HTTP mode (fallback)

```bash
python -m simulator.cli stream \
    --http-url http://localhost:8001 \
    --interval 5 \
    --transformer-id TX-001
```

---

## Historical Replay

```bash
python -m simulator.cli replay \
    path/to/CurrentVoltage.csv \
    path/to/Overview.csv \
    path/to/Power.csv \
    --speed 10 \
    --transformer-id TX-001
```

Speed multipliers: 1x (realtime), 5x, 10x, 50x

The adapter translates Kaggle column names (VL1, IL1, OTI, etc.) to canonical
field names. VL12, VL23, VL31 are excluded per dataschema.md.

---

## Testing

```bash
cd simulator
python -m pytest tests/ -v
```

Tests cover:
- Schema conformance (canonical field names, required fields, alarm/trip values)
- Generator coherence (power follows current, oil temp > ambient, energy cumulative)
- Fault injection (each scenario modifies expected fields, records remain valid)

---

## Reset Procedure

```bash
# Via CLI
python -m simulator.cli reset --http-url http://localhost:8001

# Via script
bash scripts/reset.sh

# Via Docker
docker compose down -v
docker compose up --build
```

---

## Important Constraints

1. **Canonical fields only** - The simulator NEVER invents custom variable names.
   All output uses `dataschema.md` canonical field names.

2. **No silent zero-fill** - Missing data stays `null`, never converted to `0`
   (dataschema.md principle 6).

3. **Excluded fields** - VL12, VL23, VL31 are never generated or passed through
   (dataschema.md principle 7).

4. **Physically coherent data** - Load drives current, current drives power,
   power drives thermal response. Variables are NOT independently random.

5. **Future data compatibility** - The simulator does not assume the Kaggle
   dataset is permanent. New data sources flow through Source -> Adapter ->
   Canonical Schema (dataschema.md principle 5).
