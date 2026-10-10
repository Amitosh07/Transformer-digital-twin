# H04 — API-driven React monitoring execution

Date: 2026-10-09. Frontend implementation and focused verification are ready
for manual team review. Live backend-to-browser acceptance remains blocked;
this report does not close the H02/H03 SQL or broker gates.

## Baseline and scope

Read [H04 specification](../../phases/04_FRONTEND_API_MONITORING.md), the
[verified contract](../../contracts/hackathon-v1.1.md), relevant architecture,
gap, acceptance and RUL/energy documents, H00 display fixtures, and H01–H03
execution reports. Actual backend schemas/routes were used for interface
integration; absent paths were located through their existing counterparts
(latest schema is `backend/app/schemas/state.py`, lifecycle routes are
`alerts_read.py` and `maintenance_read.py`). No prior suites were rerun.

Read-only preflight outputs:

```text
git branch --show-current
develop
git rev-parse HEAD
29dcfaf5e12ef50446d1106c4994a721dc802476
git status --short
Existing H00–H03 modifications/untracked artifacts; no frontend changes.
```

The full initial status was inspected in the execution session. A temporary
SHA-256 baseline recorded 121 pre-existing modified/untracked individual files.
Final comparison: **121 checked, zero changed or missing**. New H04 paths are
restricted to frontend and this report. Branch/HEAD remained unchanged.
No commits, pushes, merges, resets, cleanup, or production backend/ML/simulator/
Modbus/Compose changes. H00 contract remains 1.1.0; no model/artifact versions
were changed. H00/H01/H02/H03 reports and evidence remain untouched.

## Exact changed paths

Created:

```text
frontend/.env.example
frontend/H04_MONITORING.md
frontend/src/api/client.ts
frontend/src/api/contracts.ts
frontend/src/components/ResourceCards.tsx
frontend/src/hooks/usePolling.ts
frontend/src/monitoring.ts
frontend/tests/client.test.ts
frontend/tests/fixtures.ts
frontend/tests/polling.test.tsx
frontend/tests/resources.test.tsx
frontend/tests/setup.ts
frontend/tests/studio.test.tsx
frontend/vitest.config.ts
docs/hackathon_readiness/execution/H04_FRONTEND_API_MONITORING.md
```

Modified:

```text
frontend/package.json
frontend/package-lock.json
frontend/src/components/Architecture.tsx
frontend/src/components/FeaturesGrid.tsx
frontend/src/components/Footer.tsx
frontend/src/components/HealthIndexDial.tsx
frontend/src/components/Hero.tsx
frontend/src/components/ImpactMetrics.tsx
frontend/src/components/InteractiveTwinStudio.tsx
frontend/src/components/PipelineWalkthrough.tsx
frontend/src/components/PrescriptiveActionCard.tsx
frontend/src/components/Problem.tsx
frontend/src/components/Roadmap.tsx
frontend/src/components/Solution.tsx
frontend/src/components/Team.tsx
frontend/src/components/ThermalResidualChart.tsx
frontend/src/types.ts
```

Small edits outside the studio remove unsupported IEEE compliance/model claims
and performance numbers. React/Vite, Tailwind styling, single-page layout,
health dial and SVG thermal chart remain. The hero image is explicitly a
concept illustration. No hardcoded hero telemetry or simulated monitoring
scores remain. Legacy educational data/functions are unreferenced by the
monitoring production dependency path; their types are explicitly labelled.

## API contracts and consuming views

Default API base: `http://127.0.0.1:8001`, configurable through
`VITE_API_BASE_URL` without `/api/v1`. The backend README documents this local
HTTP port. Vite's frontend origin must be permitted by the backend's existing
CORS configuration. No CORS/deployment changes were made.

| GET path (under `/api/v1`) | Actual baseline shape / use |
| --- | --- |
| `/transformers?limit=50&offset=…` | `Page[TransformerOut]`; selector and paged portfolio |
| `/transformers/{id}/latest` | `LatestStateOut`; nullable telemetry/analytics, availability and global open-alert count |
| `/transformers/{id}/telemetry` | `Page[TelemetryPoint]`; full nullable canonical observations/acquisition |
| `/transformers/{id}/analytics` | `Page[AnalyticsPoint]`; thermal history/readiness; actual route omits HI/component fields |
| `/transformers/{id}/trends` | `TrendOut`; typed client support for bounded queries; current chart uses full history instead |
| `/transformers/{id}/alerts` | `Page[AlertOut]`; INFO/WARNING/CRITICAL, OPEN/ACKNOWLEDGED/RESOLVED |
| `/transformers/{id}/maintenance` | `Page[MaintenanceOut]`; NORMAL/WATCH/PLAN/URGENT, OPEN/DONE/DISMISSED |
| `/ingest/mqtt/status` | `MqttStatus`; connection, queue, committed/conflicted/dropped counters, transport timestamp/error |
| `/transformers/{id}/rul` | **Absent**; H00 `rul` resource envelope prepared for H05/H06 |
| `/transformers/{id}/energy?window=1h&anchor=latest` | **Absent**; H00 energy resource prepared for H05/H06 |

Central Zod parsing checks aware timestamps, finite numbers, enums and nulls,
and rejects inconsistent unavailable RUL/energy numerical outputs. Latest and
future resources check asset identity. HTTP, timeout, invalid response and
disconnection errors do not yield replacement data. No broad `any` API types.

History explicitly requests a one-hour event-time interval with `from`, `to`,
`anchor=latest`, `order=asc`, `limit=100`, `offset=0`. The explicit upper bound
comes from the selected latest telemetry event, including replay history;
with no observation it is the captured request time. Backend explicit-bound
semantics take precedence over anchor. Counts disclose a truncated page; this
chart is not a claim of full one-hour coverage. Open alerts/maintenance request
a bounded 24-hour event-time interval, status OPEN, limit 50. Older unresolved
actions may fall outside it; the UI identifies this scope and also displays
latest's global open-alert count. Registry pagination does not fan out history
requests across assets. Unselected assets say **Not assessed**.

HealthIndexDial now renders backend score/components/coverage/reasons.
Component weights are not present in the H02 response and are explicitly
reported as not supplied. PrescriptiveActionCard renders backend maintenance
priority, advice, reasons/evidence, trip latch and release metadata. Operational
risk/confidence/prediction stay unavailable unless explicit forecast RELEASED
and operational eligibility evidence exists. No browser HI/anomaly/risk,
maintenance, energy or RUL estimator is used.

ThermalResidualChart uses real event-time observations and exact timestamp
alignment of analytics. Model lines require ready thermal metadata and matching
declared units. Unknown/mixed units, missing values and cadence gaps break the
line; they are not fabricated zero observations. Empty history is labelled.
Winding measurement text distinguishes WTI status from temperature; oil level
does not receive an assumed percent label. Zero current/contact differs from
null and unknown contact. NameplateCard uses actual registry fields and per-field
units, verification and provenance, including temperature rises, CT/PT and loss
parameters. Populated ratings alone do not establish verification.

RULCard displays synthetic/conditional/insufficient/end-threshold/no-crossing
states, nullable hours, target/endpoint, scenario, assumptions, bounds and
coverage. Zero is displayed as `0 h`; no crossing is unavailable, not infinity.
EnergyCard displays method separately from calculation method, source/units,
window, covered total, gaps/resets, loss/efficiency and qualified advisory
savings. Future resource requests run once per asset selection. Absent/error
routes are visible; actual `latest.analytics.rul`, if supplied, remains usable
independently of the resource route. No fixture is a live fallback.

## Polling and freshness

Latest defaults to 3 seconds, configurable/clamped to 2–5 seconds. Registry
polls every 30 seconds; history, lifecycle and global MQTT diagnostics every
15 seconds. Requests have a ten-second timeout. Each poll waits for completion
before scheduling another; asset change/unmount aborts obsolete requests,
removes timers and ignores obsolete results even if cancellation is ignored
by the transport. Keyed render state prevents previous-asset data leaking into
the next selected asset. An explicit Retry action restarts the relevant request.

Last successful data and last-success time are retained separately from current
loading/error state. Failures never refresh success time or clear state to a
fake healthy result. A selected asset is not assigned an aggregate green health
status. Endpoint failures have independent visible errors; retained history is
qualified. Event time, analytics time, server receipt time and successful API
poll time are distinct. Older analytics is explicitly marked stale. Replay is
historical; legacy provenance UNKNOWN. MQTT transport messages do not update
telemetry time or prove a committed receipt for the selected observation.

Configured demo event-age default is 10 seconds (`VITE_STALE_AFTER_MS`), not a
universal operational threshold. A one-second clock updates the visible age
while API requests fail/hang. Future event times beyond this configured margin
show a clock mismatch. Gateway/broker diagnostic failures are explicit.

## Verification actually executed

Environment: Windows PowerShell, Node 22.17.0, npm 11.5.2. Added Zod 4.6.5 for
HTTP validation and Vitest 5.0.3, jsdom 29.1.1, React Testing Library 16.3.3 and
jest-dom 7.0.1 for focused tests. Exact resolved dependencies are in lockfile.
Single-worker threads are configured for predictable local resource use.

### PASSED

| Command / check | Actual result |
| --- | --- |
| Preflight branch, HEAD, status commands | develop / HEAD above; prior work recorded |
| `npm ci --ignore-scripts` (initial and final, in frontend) | exit 0; final 193 packages installed, 194 audited, zero vulnerabilities reported |
| `npm install zod` | exit 0 |
| `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom` | exit 0 |
| `npm run build` (final) | exit 0; TypeScript and Vite 8.3.3 production build succeeded |
| `npm run lint` (final) | exit 0, **16 warnings**, not warning-free |
| `npm test` (final) | exit 0; **4 files, 35 tests passed**, 7.80 seconds (earlier post-install run: 32.15 seconds) |
| `git diff --check -- frontend` (after EOF correction) | exit 0; Git notes eventual LF→CRLF normalization |
| SHA-256 comparison against temporary pre-edit baseline | 121 pre-existing files checked; zero changed/missing |
| Narrow changed-path scope/inventory check | exit 0; 32 permitted H04 paths, every path listed above |
| PowerShell resolution of added Markdown links | exit 0; all 3 report links resolve |
| Unsupported-claim search | `rg` exit 1 means no matching unsupported strings, not a failed implementation check |

Tests: client 5, polling 4, resource/null/freshness/chart tests 17, studio 9.
They cover registry selection and actual supplied latest/history values,
asset-switch races, cancellation/unmount, one-shot resources, non-overlap,
retained success time on outage, retry, timeout, identity/response errors,
partial failures, empty/no-observation states, units/config evidence, contacts,
unreleased risk, chart gaps, synthetic/conditional/zero/no-crossing/insufficient
RUL, H00 energy methods/coverage/reset/gap examples and absent resources.
The resource tests read existing H00 fixtures without editing them or invoking
the H00 suite. Desktop/mobile-width DOM checks at 1440/390 pixels pass; jsdom
does not provide visual layout or real browser transport evidence.

Lint warnings: 12 unused imports in existing surrounding presentation code,
2 Fast Refresh warnings for chart helper exports, and 2 effect-state warnings
for request lifecycle/registry selection. No lint errors. These warnings remain
visible and are not suppressed as test evidence.

### FAILED during development, corrected

- First `npm run build`: exit 1 after an overbroad text replacement changed a
  Footer import. The pre-edit baseline confirmed zero prior frontend changes;
  only this turn's damaged presentation files were repaired. Subsequent builds
  pass. Automatic approval review initially rejected HEAD reconstruction as a
  risk to prior work; after explicit baseline/diff evidence and a guard, repair
  was approved. No teammate content was overwritten.
- First focused run: three suites failed fixture import initialization with
  `ERR_INVALID_URL_SCHEME`; four polling tests passed. A diagnostic
  `npx vitest run tests/client.test.ts --pool=threads --maxWorkers=1 --reporter=verbose`
  reproduced it, exit 1. Fixed test-only file resolution, not verified fixtures.
- Next `npm test`: 30 passed, 1 failed due to an exact text matcher omitting
  the displayed backend priority prefix. Fixed matcher to retain the assertion;
  also fixed React key spreading warnings. Then 31 passed. Added timeout,
  conditional/contradictory resource and null-latest cases; final 35 pass.
- Initial `git diff --check -- frontend`: exit 1 for three added blank EOF
  lines. Corrected only H04 files; final check passes.
- Read attempts for nonexistent backend `latest.py`, `maintenance.py` and query
  helper paths failed; their actual counterparts were located/read. No interfaces
  were invented from those missing files.

### BLOCKED / acceptance not met

- Actual Node fetch probe of
  `http://127.0.0.1:8001/api/v1/transformers?limit=1&offset=0` with a two-second
  timeout: exit 1, **ECONNREFUSED**. No live API request succeeded. Live
  backend-to-browser score/reason/timestamp equality and CORS acceptance remain
  for H06. Fixture-driven frontend tests do **not** prove full-stack success.
- RUL and energy resource routes are absent from the actual H02 router. H05/H06
  must supply these frozen resources; UI failure states are implemented and
  tested without hiding their absence.
- PostgreSQL/broker/Modbus→MQTT→SQL committed-receipt gates remain blocked as
  reported in H02/H03. No SQL, migration, broker or receipt success is asserted.
- Visual desktop/mobile browser layout rehearsal and 25-asset load acceptance
  were not performed; DOM checks and paginated portfolio support are not proof.
- Component weights and richer bundle readiness not exposed by the actual
  backend schema cannot be invented by the frontend; supplied component
  readiness, version IDs and reasons are displayed, absent evidence is unknown.

### SKIPPED intentionally

H00 fixture suite, H01 ML/release/packaging suites, H02 backend/database suites,
H03 simulator/protocol suites, root deployment and H05 algorithms. No mock
backend service was presented as live infrastructure.

## Concrete supplied response → output example

Controlled frontend test response for HX-A (not a real ML inference):

```json
{
  "telemetry": {
    "transformer_id": "HX-A",
    "timestamp": "2026-10-09T00:00:00Z",
    "current_l1": 0,
    "oil_temperature": 37,
    "oil_temp_alarm": null,
    "oil_temp_trip": 0,
    "acquisition": {"source_kind": "SIMULATED", "source_name": "h00-fictional"}
  },
  "analytics": {
    "health_index": 37,
    "fault_risk": null,
    "prediction_confidence": null,
    "maintenance_priority": "WATCH",
    "maintenance_recommendation": "Inspect supplied backend evidence"
  }
}
```

This excerpt omits the remaining required fields; tests supply the full typed
response via `frontend/tests/fixtures.ts`, using H00 source/unit metadata.
The DOM displays backend HI **37**, current **0 A**, oil observation **37 in its
declared source unit**, unknown alarm, cleared trip, WATCH recommendation and
unavailable operational risk/confidence. Old event time shows a stale simulated
measurement despite a recent successful poll. The history shows the supplied
37 observation, not generated samples; unreleased/unready thermal model remains
unavailable. Controlled resource HTTP 404 responses render explicit unavailable
RUL/energy messages. No real 404 receipt/database result is inferred from them.

## Handoff and stop

[Frontend usage](../../../frontend/H04_MONITORING.md) documents exact environment,
queries, bounds and commands. H04 implementation and focused frontend evidence
are complete to the permitted scope; integrated F01/live acceptance is open.
H06 must connect real services and verify browser equality/outage/CORS/viewport
behavior. The exact next dependent phase is **H05 — RUL and energy analytics**.
H05/H06/H07 were not begun. Stop for manual team review.
