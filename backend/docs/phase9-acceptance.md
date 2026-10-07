# Final backend phase acceptance

Branch feature/backend-api, changes confined to backend/. No canonical schema, new
migration, ingestion/alert rule or ML behavior change. Existing head remains 0003.

## Final checks

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
  Git attributes pin shell entrypoints to LF for fresh Windows checkouts.
- Git whitespace/scope checks pass; all deliverables are under backend/.
- One existing Starlette/httpx TestClient deprecation warning remains.

The previous 693 tests are unchanged, including the existing OpenAPI baseline. The admin
reset endpoint is additive. New source/wording checks cover PowerShell/shell/Compose,
Docker, examples, captured JSON and the changelog, while existing guards automatically
cover new Python scripts, app modules and docs. Every API operation has a generated
reference row and an HTTP request example; the typed client is exercised against real
seeded API responses, including nullable projections.

## Fresh-stack verification

Built the final multi-stage Python 3.12 slim image on empty demo volumes. All services
became healthy; /health and /health/ready returned OK. The backend runs as UID/GID 10001,
with pytest and Ruff absent from the runtime image. Entrypoint waited for DB and applied
existing migrations before uvicorn. The dev PostgreSQL and Mosquitto containers remained
separate and unchanged.

Default host ports: HTTP 8001, PostgreSQL 55433, MQTT 51885. The broker port intentionally
leaves 51884 free for the unchanged offline-broker regression. Named demo volumes persist
across down/up. Only the newly created transformer-demo volumes were cleared for the
clean-stack verification. Service names are db,mqtt,backend for Person 4's Compose merge.

- Default seed: 2000 telemetry and analytics rows; scenarios 800 HEALTHY / 600 STRESS /
  600 FAULT including 120 recovery rows. Fixed UTC start and 30-second spacing.
- Ten oil-temperature dropout records produce null/INSUFFICIENT_DATA, not zero-filled data.
- Stub health path 90 -> 55 -> 25 -> 90; stress without flags stays 90 as required by
  unchanged stub semantics. Temperature/oil units are not asserted, and ratings are null.
- Oil alarm precedes oil trip; trip severity is CRITICAL. PLAN then URGENT maintenance
  persists; eight alert episodes are RESOLVED after recovery; maintenance remains OPEN.
- A real QoS 1 MQTT publish to transformer/TX-001/telemetry was committed, appeared in
  latest and incremented consumer counters without errors.
- Duplicate HTTP seed inserted zero telemetry/analytics/lifecycle rows, counting 2000 duplicates.
- Reset deleted all measurement/analytics/lifecycle/run rows atomically; empty latest/pages
  and scenarios were verified. Transformer config was retained, and MQTT counters were retained.
- Reseeding through HTTP reproduced the same business counts and ordered canonical telemetry
  hash as in-process seeding: b09074ed9f728758903fef1e08a05bfb26a50a14ef042acfe408f8435c755045.
  Generated database IDs and server timestamps are excluded from this deterministic hash.
- HTTP reset was verified disabled (404) on Compose; real PostgreSQL tests cover configured
  token success, missing/wrong/unconfigured tokens, production refusal, optional asset
  deletion and atomic rollback on a partial-delete failure.
- Real API samples were captured from this seed; write/lifecycle examples use TX-CAPTURE
  and do not modify TX-001. The API document is generated from live OpenAPI and captures.

Raw stack evidence: [demo-verification.json](demo-verification.json). The verification
script is scripts/verify_demo_stack.py. Tests use real PostgreSQL plus the existing local
MQTT broker; no SQLite substitute is used.

## Demo commands

```powershell
cd C:\Transformer-backend\backend
./scripts/demo.ps1 up
./scripts/demo.ps1 seed
Invoke-RestMethod http://127.0.0.1:8001/health/ready
Invoke-RestMethod http://127.0.0.1:8001/api/v1/transformers/TX-001/latest
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers/TX-001/alerts?anchor=latest&status=RESOLVED'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers/TX-001/maintenance?anchor=latest'
./scripts/demo.ps1 reset -Yes
./scripts/demo.ps1 seed
./scripts/demo.ps1 down
```

See [docker.md](docker.md) for logs, direct Compose commands, host port overrides,
nameplate/HTTP seed options, token-enabled reset, counter semantics and Compose merge.
[handoff.md](handoff.md) covers Person 1/3/4; [api.md](api.md) consolidates every endpoint
and captured JSON; [known-limitations.md](known-limitations.md) records remaining operational
and integration limits. [PR_DESCRIPTION.md](PR_DESCRIPTION.md) is ready for develop review.

All requested local Docker, PostgreSQL, MQTT and demo checks were available. Actual
Person-1 ML code/service was not supplied; demo uses stub, with existing adapter tests
covering Python/HTTP contracts and failures. General auth and durable queues/jobs remain
known limitations, rather than missing final-phase verification.

Full file list: [FILES.md](FILES.md), final phase section.
