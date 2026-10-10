# API monitoring (H04)

Use `npm ci --ignore-scripts`, then `npm run dev`. Keep the existing React/Vite
stack. Copy `.env.example` to a local `.env` if needed; Vite reads these settings
at startup/build time. `VITE_API_BASE_URL` is an origin/base prefix **without**
`/api/v1`; default `http://127.0.0.1:8001`. Set it to the actual backend instance.
The backend owner must allow the frontend's origin through its existing CORS
configuration. H04 does not change backend settings or deployment services.

`VITE_POLL_INTERVAL_MS` defaults to 3000 and is clamped to 2000–5000.
`VITE_STALE_AFTER_MS` defaults to 10000: this is a configured demo event-age
threshold for the nominal five-second simulator, not a universal physical limit.
Requests time out after ten seconds. Only the selected asset is monitored;
other portfolio entries say **Not assessed**. Registry pages contain at most 50
assets. Latest polls do not overlap. History and lifecycle queries run every
15 seconds, registry every 30 seconds, and MQTT diagnostics every 15 seconds.

History requests explicitly bound `from` and `to` to one hour ending at the
selected latest measurement event, using aware UTC timestamps, `anchor=latest`,
`order=asc`, `limit=100`, `offset=0`. This is a bounded page; omitted observations
are disclosed and are not evidence of full coverage. Open alerts/maintenance
use a bounded 24-hour event-time window and a maximum 50-row page. Older open
actions can fall outside it; latest's global open-alert count is displayed.
No history requests fan out across the portfolio. Gateway transport time never
updates measurement time. Historical replay retains its historical label.

RUL and energy capability requests run once per asset selection. The H02
baseline does not implement `/api/v1/transformers/{id}/rul` or
`/api/v1/transformers/{id}/energy?window=1h&anchor=latest`. Actual 404/failure
responses remain visible; no mock result or client estimator replaces them.
An actual persisted `latest.analytics.rul` can be displayed independently of
the resource route. The typed client is prepared for H00-shaped resources.
It also exposes the existing bounded `/trends` API; the current chart consumes
full telemetry/analytics history instead of aggregated buckets.

`src/api/contracts.ts` validates HTTP JSON, preserving explicit nulls and known
enums. `src/types.ts` and `src/data/` are legacy educational simulation code;
the monitoring dashboard and production entry point do not import their data
or calculations. Unknown units/provenance, unknown contacts, unreleased risk,
configuration evidence and analytics readiness are displayed explicitly.

Verification: `npm run build`, `npm run lint`, `npm test`. The minimal added
runner is Vitest with jsdom and React Testing Library; Zod provides runtime
response validation. `tests/fixtures.ts` reads the verified H00 examples/oracles
only for tests. Controlled fetch fixtures test UI behavior, not SQL commits,
real broker delivery or live backend-to-browser acceptance. jsdom viewport
checks are DOM checks, not visual browser layout proof. See the H04 execution
report for actual results and remaining gates.
