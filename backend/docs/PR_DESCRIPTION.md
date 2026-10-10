# Complete Transformer Digital Twin backend, demo and handoff

Merge **feature/backend-api** into **develop**. The backend now accepts canonical
telemetry over HTTP/MQTT/replay, stores validated nullable telemetry and versioned ML
analytics, serves dashboard state/history/trends, and maintains alert/maintenance
lifecycles. The final phase supplies a deterministic demo, safe reset tools, a runnable
Compose stack and team integration documentation.

## Scope and phases

- Phases 1â€“3: PostgreSQL/Alembic, Pydantic v2 canonical contracts, safe stub/Python/HTTP ML adapters.
- Phases 4â€“5: idempotent single/batch/replay ingestion, quality stats and MQTT delivery/status/shutdown.
- Phases 6â€“7: dashboard reads/SQL trends/demo metadata, alert lifecycle and maintenance persistence.
- Phase 8: measured batch optimization, request correlation, readiness, OpenAPI/source/wording guards.
- Final phase: fixed UTC/seeded canonical scenarios with dropout/recovery, guarded atomic reset,
  multi-stage non-root Docker image, persistent DB/broker stack and PowerShell runner,
  real captured API samples, typed client, endpoint examples and Person 1/3/4 handoff.

All changes are under backend/. Existing migration head is 0003; no new migration,
canonical schema or ingestion/alert/ML behavior change is introduced in the final phase.
Default nameplate remains null. The optional reset endpoint is additive, disabled by
default, requires a configured admin token and refuses production.

## Verification

- **722 passed, no skips**, in **215.15 seconds**, using real PostgreSQL 16 and Mosquitto.
  All 693 earlier tests remain unmodified; 29 new final-phase cases pass.
- Independent package coverage: **services 98.88% (704/712 lines)**,
  **repositories 98.53% (269/273 lines)**. Both pass the 80% gate; combined coverage is 98.78%.
- Ruff check and Ruff format --check pass. Existing source-name/wording/OpenAPI guards,
  added operational/example guards, every-endpoint documentation coverage and typed-client
  tests pass. Existing schema/ORM and migration checks pass; no new migration is introduced.
- Seed idempotency/determinism, scenario assertions, reset --yes and production refusal,
  endpoint default-disabled/token access and rollback/FK-safe optional asset deletion pass.
- Fresh Compose build/health/readiness, real MQTT publishing, empty reset and identical
  reseed hashes pass. Runtime non-root identity and absence of dev dependencies pass.
- Git whitespace/scope checks pass; all deliverables are under backend/.
- One existing Starlette/httpx TestClient deprecation warning remains.

Fresh separate Docker stack was built from the checked-in Dockerfile/Compose config on
new named volumes, with /health and /health/ready returning OK. Default demo creates
2000 telemetry/analytics rows, 800/600/600 scenario rows, ten insufficient-input rows,
eight resolved alerts and PLAN/URGENT maintenance. Health moves 90 -> 55 -> 25 -> 90.
Real MQTT publishing ingests. Duplicate seed inserts zero rows; reset/reseed retains
identical ordered telemetry SHA256 and business counts. Non-root UID 10001 and absence
of pytest/ruff in the runtime were verified. Captured JSON samples come from that API,
with write samples on a separate TX-CAPTURE asset.

Phase 8's paired 10000-row profiles are 76.147 -> 9.735 s initial, 38.212 -> 1.146 s
duplicate, and 29.299 -> 4.068 s no-ML; see performance.md for instrumentation and limits.
The previous coverage run passed 693 tests, with services 98.99% and repositories 98.44%.
Final result and commands are in [phase9-acceptance.md](phase9-acceptance.md).

## How to verify

```powershell
cd C:\Transformer-backend\backend
./scripts/demo.ps1 up
./scripts/demo.ps1 seed
Invoke-RestMethod http://127.0.0.1:8001/health/ready
Invoke-RestMethod http://127.0.0.1:8001/api/v1/transformers/TX-001/latest
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers/TX-001/alerts?anchor=latest&status=RESOLVED'
.venv/Scripts/python.exe scripts/verify_demo_stack.py
./scripts/demo.ps1 down
```

Set real PostgreSQL TEST_DATABASE_URL and MQTT_TEST_HOST/MQTT_TEST_PORT as documented in
README, then run pytest and both Ruff checks. Fixtures use disposable databases.
Fresh-stack verification resets the Compose demo, so finish publishers/replays first.
Use docker.md for logs, ports, seeding/reset and integration into the team's Compose file.

## Risks and review focus

- No general API auth, local demo credentials and anonymous broker; reset token protects only reset.
- In-memory MQTT acknowledgement precedes commit, and BackgroundTasks replay is not durable.
- Stub scores are placeholders; actual ML integration and unverified units remain open team questions.
- Per-transformer writer locks serialize lifecycle updates; concurrent offset pagination can shift.
- Review canonical/null/UTC contracts, schema-version/history boundaries, proxy-risk wording,
  prepared partial-index predicates and the sole ingestion write entry point.
- Check migrations 0001â€“0003 on your database, optional reset access/production guard and global
  deletion scope, non-root container startup/shutdown, volumes and port/DNS mappings.
- Review captured API examples, latest anchoring, alert timestamp/last_seen_at semantics,
  recovery chain, guard coverage and exact Person 1/3/4 integration instructions.

Full created/changed file inventory: [FILES.md](FILES.md).
