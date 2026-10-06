# Backend + Database

## Owner

**Person 2 — Backend + Database**

This folder contains the FastAPI backend, PostgreSQL database layer, ingestion services, API endpoints, validation, and integration with the ML/Twin layer.

---

## 1. Mission

Build the service layer that connects:

```text
ML/Twin
   ↕
Backend
   ↕
PostgreSQL
   ↕
Frontend
   ↕
Simulator
```

The backend must expose stable APIs so the frontend does not need access to ML internals or PostgreSQL directly.

---

## 2. Important Documents

Read before implementation:

```text
../dataschema.md
../mlcontract.md
../docs/
```

### `dataschema.md`

Defines canonical telemetry fields.

### `mlcontract.md`

Defines ML/Twin analytical inputs and outputs.

The backend must follow these contracts.

---

## 3. Responsibilities

### FastAPI

Build:

- application structure
- configuration
- API versioning
- request validation
- response validation
- exception/error handling
- service health checks
- OpenAPI documentation

---

## 4. PostgreSQL

Design storage for:

### Transformer metadata

Examples:

```text
transformer_id
rated_power_kva
rated_voltage_hv
rated_voltage_lv
rated_current_a
cooling_class
oil_type
```

### Telemetry

Store canonical telemetry including:

```text
timestamp
transformer_id
electrical measurements
thermal measurements
oil condition
protection states
power
power factor
```

### Derived analytics

Store:

```text
loading_percent
thermal_model_temperature
anomaly_score
anomaly_flag
health_index
fault_risk
predicted_fault
maintenance_priority
maintenance_recommendation
reason_codes
```

### Alerts

Store alert information including:

```text
severity
timestamp
trigger
reason
evidence
status
```

---

## 5. Database Requirements

Use:

```text
SQLAlchemy
Alembic
PostgreSQL
```

Implement proper migrations.

For telemetry/time-series queries, use appropriate indexes, particularly around:

```text
transformer_id
timestamp
```

Handle:

- time windows
- pagination
- timezone consistency
- duplicate handling
- validation

---

## 6. API Version

Use:

```text
/api/v1/
```

The API must be versioned so future changes do not unexpectedly break the frontend.

---

## 7. Required API Surface

Implement at minimum:

```text
GET /health

GET /api/v1/transformers

GET /api/v1/transformers/{id}/latest

GET /api/v1/transformers/{id}/telemetry

GET /api/v1/transformers/{id}/health

GET /api/v1/transformers/{id}/alerts

GET /api/v1/transformers/{id}/maintenance

POST /api/v1/telemetry

POST /api/v1/simulate/replay
```

Equivalent endpoint naming can be used if documented and agreed by the team.

---

## 8. Canonical Telemetry Ingestion

The API must accept canonical fields.

Example:

```json
{
  "transformer_id": "TX-001",
  "timestamp": "2026-10-06T11:30:00Z",
  "current_l1": 49.8,
  "current_l2": 50.2,
  "current_l3": 48.9,
  "oil_temperature": 57.4,
  "ambient_temperature": 31.2
}
```

Do not expose or require Kaggle-specific source column names in the API.

---

## 9. ML Integration

The backend consumes the output defined in:

```text
../mlcontract.md
```

The backend should not depend on internal ML dataframes or notebooks.

Example ML output:

```json
{
  "health_index": 68.4,
  "anomaly_score": 0.82,
  "anomaly_flag": true,
  "fault_risk": 0.67,
  "predicted_fault": "THERMAL_STRESS",
  "maintenance_priority": "PLAN"
}
```

Persist these results where appropriate.

---

## 10. Version Metadata

Where applicable, store:

```text
schema_version
feature_version
model_version
training_dataset_version
```

This allows the backend/dashboard to identify which ML version produced a result.

---

## 11. Frontend Contract

The frontend must only communicate through the API.

The frontend must NOT:

```text
read PostgreSQL directly
import ML code
read ML dataframes
depend on simulator internals
```

The frontend consumes:

```text
FastAPI JSON
```

only.

---

## 12. Simulator Integration

The simulator will eventually send canonical telemetry through:

```text
HTTP API
```

or:

```text
MQTT / equivalent live transport
```

The backend should normalize/validate the incoming canonical data and pass it through the same storage/analytics pipeline.

---

## 13. Validation

Validate:

- required fields
- data types
- timestamps
- missing critical values
- numeric ranges
- boolean/status values
- schema version

Do not silently convert invalid data.

---

## 14. Testing

Implement tests for:

### API

- health endpoint
- telemetry ingestion
- historical queries
- latest state
- Health Index
- alerts
- maintenance

### Database

- migrations
- model relationships
- inserts
- time-window queries

### Integration

Test:

```text
Canonical telemetry
       ↓
FastAPI
       ↓
PostgreSQL
       ↓
ML output
       ↓
API response
```

---

## 15. Demo Bootstrap

Provide:

- seed data
- database initialization
- migration commands
- demo setup
- environment configuration template
- reset/clear procedure if needed

The system should be easy for another team member to start.

---

## 16. Deliverables

This folder must eventually contain:

- FastAPI application
- API routes
- Pydantic schemas
- PostgreSQL models
- SQLAlchemy configuration
- Alembic migrations
- ingestion services
- query services
- ML integration
- API tests
- database tests
- OpenAPI documentation
- demo bootstrap

---

## 17. Definition of Done

Backend is complete when:

```text
Canonical telemetry
       ↓
FastAPI
       ↓
PostgreSQL
       ↓
ML analytics
       ↓
Stable API response
       ↓
Frontend
```

works reliably.

The dashboard developer must be able to build the complete UI without:

```text
accessing PostgreSQL directly
```

or:

```text
importing ML internals
```

---

## 18. Ownership

Person 2 owns:

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic/API schemas
- ingestion
- database queries
- ML integration
- validation
- backend tests

Use `dataschema.md`, `mlcontract.md`, and the eventual API contract as the module boundaries.
