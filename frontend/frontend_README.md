# Frontend + Dashboard

## Owner

**Person 3 — Frontend + Dashboard**

This folder contains the interactive transformer monitoring dashboard.

The dashboard should make the condition of the transformer understandable within seconds while allowing technical investigation through trends, alerts and supporting evidence.

---

## 1. Mission

Build the presentation layer of the Transformer Digital Twin.

The dashboard must show:

```text
Current Condition
       ↓
Digital Twin State
       ↓
Health Index
       ↓
Anomalies / Fault Risk
       ↓
Maintenance Recommendation
```

---

## 2. Important Documents

Read before implementation:

```text
../dataschema.md
../mlcontract.md
../docs/
```

The dashboard must use canonical field names and backend API responses.

---

## 3. Backend Boundary

The frontend communicates with:

```text
FastAPI
```

only.

Do NOT:

```text
read PostgreSQL directly
import ML Python code
import ML dataframes
read simulator internals
```

---

## 4. Development Strategy

The frontend does not need to wait for the backend.

Initially use mock API responses.

Example:

```json
{
  "transformer_id": "TX-001",
  "health_index": 84.5,
  "loading_percent": 64.2,
  "oil_temperature": 57.4,
  "ambient_temperature": 31.4,
  "anomaly_score": 0.12,
  "anomaly_flag": false,
  "fault_risk": 0.08,
  "maintenance_priority": "NORMAL"
}
```

Once the backend is available:

```text
Mock API
   ↓
Replace with FastAPI
```

The UI structure should not need to be rewritten.

---

# 5. Dashboard Sections

## 5.1 Overview

Show immediately:

```text
Transformer status
Health Index
Loading
Oil temperature
Ambient temperature
Fault risk
Active alerts
Maintenance priority
```

The judge should understand the transformer condition within seconds.

---

## 5.2 Live Monitoring

Display canonical measurements such as:

### Electrical

```text
phase_voltage_l1
phase_voltage_l2
phase_voltage_l3

current_l1
current_l2
current_l3

neutral_current
```

### Thermal

```text
oil_temperature
winding_temperature
ambient_temperature
```

### Oil

```text
oil_level
```

### Protection

```text
oil_temp_alarm
oil_temp_trip
magnetic_oil_gauge_alarm
```

### Power

```text
active_power_total
apparent_power_total
reactive_power_total
energy_kwh
```

### Power Factor

```text
power_factor_l1
power_factor_l2
power_factor_l3
```

---

## 5.3 Digital Twin View

This is one of the most important parts of the dashboard.

Display:

```text
Observed thermal state
        vs
Model thermal state
```

For example:

```text
Observed Temperature
Model Temperature
Thermal Residual
```

Also show:

```text
Loading / Utilization
Thermal state
Current condition
```

The dashboard should make it visually clear that the project is a Digital Twin rather than a normal telemetry dashboard.

---

## 5.4 Health Index

Show:

```text
Health Index: 84 / 100
```

Also show component contributions:

```text
Thermal
Electrical
Loading
Oil
Alarm
Anomaly
```

Where available, show the major reasons behind the score.

Example:

```text
Health Index: 68

Main contributors:
- High oil temperature
- Current imbalance
- Elevated thermal residual
```

---

## 5.5 Trends

Provide selectable time windows.

Show trends for:

```text
Current
Voltage
Loading
Oil temperature
Ambient temperature
Power
Power factor
Anomaly score
Health Index
Fault risk
```

Where appropriate, allow comparison:

```text
Observed thermal temperature
vs
Model thermal temperature
```

---

## 5.6 Alerts

Display:

```text
Severity
Timestamp
Trigger
Current evidence
Reason
Recommended action
```

Example:

```text
HIGH

Rapid temperature rise detected

Evidence:
Oil temperature ↑
Loading ↑
Thermal residual ↑

Action:
Inspect cooling performance.
```

---

## 5.7 Maintenance

Show:

```text
Maintenance priority
Maintenance recommendation
Reason codes
Supporting evidence
```

Allowed priorities:

```text
NORMAL
WATCH
PLAN
URGENT
```

---

## 5.8 Historical Analysis

Allow the user to select a time range and inspect:

```text
Telemetry
Health Index
Anomaly score
Fault risk
Alerts
Maintenance recommendations
```

---

## 5.9 Demo Mode

Clearly indicate whether the dashboard is displaying:

```text
Historical data
Replayed data
Simulated data
Live data
```

The judge must never be confused about the origin of the displayed data.

---

# 6. Recommended Navigation

A possible structure:

```text
Dashboard
├── Overview
├── Live Monitoring
├── Digital Twin
├── Trends
├── Alerts
├── Maintenance
└── Historical
```

The exact navigation implementation can be chosen by the frontend developer.

---

# 7. Reusable Components

Create reusable components for:

```text
Metric cards
Status indicators
Health Index
Alert cards
Trend charts
Thermal comparison chart
Maintenance recommendation card
Transformer status
```

Avoid duplicating visualization logic.

---

# 8. Technology

Preferred baseline:

```text
Streamlit
Plotly
```

An equivalent frontend stack can be used only after team agreement.

---

# 9. API Integration

Build a dedicated API client layer.

For example:

```text
frontend/
├── api/
├── components/
├── pages/
└── ...
```

The UI should consume backend responses rather than constructing its own analytics.

---

# 10. Error States

The dashboard should handle:

```text
Backend unavailable
No telemetry
Missing data
Insufficient ML data
No active alerts
No historical data
```

Do not display misleading zeros when data is actually missing.

---

# 11. Demo Requirements

The final dashboard must support a judging sequence such as:

```text
Healthy
   ↓
Stress
   ↓
Fault
   ↓
Alert
   ↓
Health degradation
   ↓
Maintenance recommendation
```

The experience should be deterministic and easy to follow.

---

# 12. Deliverables

This folder must eventually contain:

- Interactive dashboard
- Reusable components
- Plotly charts
- API client
- Overview page
- Live monitoring
- Digital Twin thermal visualization
- Health Index view
- Trends
- Alerts
- Maintenance recommendations
- Historical analysis
- Demo controls
- Screenshots/GIFs for documentation

---

# 13. Definition of Done

The dashboard is complete when a judge can:

1. See current transformer condition.
2. See the Health Index.
3. Understand why the condition is good/bad.
4. See electrical and thermal trends.
5. See Digital Twin model-vs-observed behavior.
6. See alerts.
7. Understand fault risk.
8. See maintenance recommendations.

All of this must be possible without opening source code.

---

## 14. Ownership

Person 3 owns:

- frontend
- dashboard UX
- visualization
- API client
- charts
- metric/status components
- Health Index display
- alerts
- maintenance UI
- historical views
- demo UX

Do not change backend or ML contracts independently.
