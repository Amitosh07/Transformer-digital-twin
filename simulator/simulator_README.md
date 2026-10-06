# Simulator + DevOps

## Owner

**Person 4 — Simulator + DevOps**

This folder contains synthetic transformer telemetry generation, historical replay, fault-injection scenarios, streaming/live simulation, Docker/Compose support, testing, and demo automation.

---

## 1. Mission

Make the Digital Twin:

- repeatable
- demonstrable
- testable
- portable
- extensible

The simulator should generate valid canonical transformer telemetry and intentionally create abnormal scenarios so the team can demonstrate the complete Digital Twin response.

---

## 2. Important Documents

Read before implementation:

```text
../dataschema.md
../mlcontract.md
../docs/
```

The simulator must follow `dataschema.md`.

---

## 3. Critical Rule

The simulator must generate:

```text
CANONICAL FIELDS
```

It must NOT create a second custom variable naming system.

Do not invent simulator-only replacements for:

```text
current_l1
current_l2
current_l3
oil_temperature
ambient_temperature
...
```

Every generated record should conform to the canonical schema.

---

# 4. Simulator Modes

The simulator should eventually support:

```text
1. Normal synthetic operation
2. Historical replay
3. Fault injection
4. Live/streaming simulation
```

---

# 5. Normal Synthetic Data

Generate realistic-looking canonical telemetry for a transformer operating normally.

The generator should produce coherent relationships between:

```text
load
current
power
temperature
ambient conditions
power factor
oil condition
```

Do not generate each variable independently if that creates physically nonsensical behavior.

---

# 6. Historical Replay

Replay the public historical dataset at adjustable speed.

Example:

```text
Dataset
   ↓
Canonical Adapter
   ↓
Replay Engine
   ↓
Backend
   ↓
Dashboard
```

The replay system should allow control over the playback speed.

Potential examples:

```text
1x
5x
10x
50x
```

The exact implementation is flexible.

---

# 7. Fault Injection

Build deterministic fault scenarios.

Required scenarios include:

```text
OVERLOAD
HIGH_TEMPERATURE
RAPID_TEMPERATURE_RISE
CURRENT_IMBALANCE
VOLTAGE_DEVIATION
LOW_OIL_LEVEL
ALARM/TRIP ACTIVATION
SENSOR_ANOMALY
```

Each scenario should produce an expected response.

---

# 8. Scenario Metadata

Every fault scenario should have metadata such as:

```text
scenario_id
start_time
end_time
severity
injected_variables
expected_response
```

Example:

```json
{
  "scenario_id": "SCN_OVERLOAD_01",
  "severity": "HIGH",
  "injected_variables": [
    "current_l1",
    "current_l2",
    "current_l3"
  ],
  "expected_response": [
    "loading increases",
    "thermal stress increases",
    "anomaly score increases",
    "health index decreases",
    "maintenance priority increases"
  ]
}
```

---

# 9. Important Demonstration Chain

The simulator should be capable of producing:

```text
Fault Injection
      ↓
Telemetry changes
      ↓
Loading / Thermal response
      ↓
Digital Twin response
      ↓
Anomaly detected
      ↓
Health Index degradation
      ↓
Fault risk increase
      ↓
Alert
      ↓
Maintenance recommendation
```

This chain is one of the most important demonstrations of the entire project.

---

# 10. Streaming

Implement:

```text
MQTT
```

or an equivalent live-streaming mechanism if the team agrees on another transport.

The stream should carry canonical telemetry.

Example conceptual flow:

```text
Simulator
   ↓
MQTT
   ↓
Backend Consumer
   ↓
PostgreSQL
   ↓
ML/Twin
   ↓
Dashboard
```

---

# 11. Docker / Docker Compose

Create a reproducible environment for the team.

The final stack should eventually be able to start:

```text
PostgreSQL
Backend
Simulator
Frontend
MQTT broker (if used)
```

through Docker Compose.

The exact service names can be decided during implementation.

---

# 12. One-Command Startup

The team should be able to start the project with a simple workflow such as:

```bash
docker compose up
```

or an equivalent documented command.

Provide:

```text
startup
reset
seed
demo
```

commands/scripts where appropriate.

---

# 13. Testing

Implement:

### Schema tests

Verify generated records conform to:

```text
dataschema.md
```

### Replay tests

Verify historical replay works.

### Scenario tests

Verify each fault scenario changes the expected variables.

### Service tests

Verify:

```text
backend starts
database starts
simulator starts
frontend starts
```

### End-to-end tests

Verify:

```text
Simulator
   ↓
Backend
   ↓
Database
   ↓
ML/Twin
   ↓
Dashboard/API response
```

---

# 14. Demo Scenarios

Prepare at least 3–5 deterministic judging scenarios.

Recommended set:

```text
SCENARIO 1
Healthy

SCENARIO 2
Overload

SCENARIO 3
Thermal Stress

SCENARIO 4
Current Imbalance

SCENARIO 5
Low Oil / Alarm
```

Each scenario should have an expected result.

---

# 15. Demo Reset

The team must be able to return the application to a clean state.

Provide a documented reset procedure.

Example:

```text
reset database
reset simulator state
restart stream
```

The goal is to make the final demo repeatable.

---

# 16. Future PowerNext Data

The simulator must not assume that the public Kaggle dataset is the permanent input format.

Future data should still flow through:

```text
Source
   ↓
Adapter
   ↓
Canonical Schema
   ↓
Simulator / Processing
```

Do not modify the whole simulator merely because organizer column names differ.

---

# 17. Deliverables

This folder must eventually contain:

- Synthetic telemetry generator
- Historical replay engine
- Fault-injection library
- Scenario metadata
- Streaming/live simulator
- MQTT/equivalent support
- Dockerfile(s)
- Docker Compose
- Smoke tests
- Integration tests
- Demo seed/reset scripts
- Demo runbook

---

# 18. Definition of Done

Simulator/DevOps is complete when:

```text
Fresh machine
      ↓
Start stack
      ↓
Load/replay data
      ↓
Inject known fault
      ↓
Expected telemetry change
      ↓
Expected anomaly/health/risk response
      ↓
Maintenance recommendation
```

works reliably and repeatably.

---

## 19. Ownership

Person 4 owns:

- simulator
- synthetic SCADA data
- historical replay
- fault injection
- streaming
- MQTT/equivalent
- Docker
- Docker Compose
- smoke tests
- integration testing
- deployment support
- demo reset/runbook

The simulator must always produce data compatible with `dataschema.md`.
