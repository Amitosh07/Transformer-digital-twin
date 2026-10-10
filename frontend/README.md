# Transformer Digital Twin — Operations Console

React/Vite/TypeScript monitoring UI. The application opens directly to the
registry-backed asset overview. Historical marketing/educational components
remain preserved, but the production entry point does not mount or import them.
All monitoring values come from FastAPI. There is no local analytics or sample fallback.

## Run locally

Use the existing lockfile and Node version compatible with Vite 8 (tested Node 22.17).
With dependencies already installed, `npm run dev` from this directory starts Vite.
On a fresh installation use `npm ci --ignore-scripts`. Vite binds to loopback.
`.env.example` documents `VITE_API_BASE_URL`, selected polling and demo staleness.
The direct API default is `http://127.0.0.1:8001`; this origin must allow the
frontend through CORS. Do not include `/api/v1` in that setting.

The existing Docker UI can remain running at 5173. To inspect current source on
Windows PowerShell without rebuilding any container:

```powershell
cd frontend
$env:VITE_API_BASE_URL = '/'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

Open `http://127.0.0.1:5174`. In this same-origin development mode Vite forwards
`/api` to the established backend at `http://127.0.0.1:8001`; it returns actual
responses/errors. The proxy is development-only. Production builds still use
the configured API origin and existing CORS/deployment conventions. Ctrl+C
stops only this development server. No backend, source or database reset is needed.
The ten-transformer change also served the current build from the existing Docker
frontend at 5173 without rebuilding its image. See the
[ten-transformer report](../docs/hackathon_readiness/execution/TEN_TRANSFORMER_FLEET.md)
for the current runtime and verified browser evidence.

## Navigation and request budget

Overview fetches active backend registry pages (50 rows/request), deduplicates IDs,
supports ID/name search and shows five cards/page. The backend supplies the ordered
ten-transformer fleet: Page 1 of 2 / Page 2 of 2, without a frontend ID list.
Historical identities remain available through scope=all and individual APIs.
Removed active identities stop supplying detail data. Status/alarm filters apply to
the visible page; other pages are not silently assessed. Latest card requests
have at most3 concurrent calls, repeat15 seconds after completion and never fetch
portfolio history. Every asset has its own response/error/last-success state.
Selecting an asset stops overview polling and opens the equipment-centred view.

Selected latest polls every2–5 seconds (configured default3); registry refreshes
60 seconds, MQTT diagnostics15 seconds. Active monitoring/thermal tabs request
only the newest300 telemetry/analytics rows in an explicit one-hour event-time
window every15 seconds. Rows are restored to chronological display order; partial
coverage is disclosed. Alarms/maintenance retrieve the most recent30 records
inside a24-hour event-time window using the actual ascending API's offset pages.
No alarm acknowledgement/control is sent. Maintenance-only RUL polls15 seconds;
projection and one-hour energy poll30 seconds. These intervals do not restart
whenever telemetry event time changes. Superseded requests abort/ignore their
results; unmount cancels timers. HTTP requests time out after10 seconds.

## Supported inputs and limitations

| Panel | Existing backend input | Honest limitation |
|---|---|---|
| Asset overview | `/api/v1/transformers`, `/{id}/latest` | Null/error is not healthy; registry values do not establish verification. |
| Equipment / electrical | Latest canonical voltage/current/power, contacts and analytics | A temperature trip or generic anomaly is not a confirmed short circuit. WTI status is not temperature. |
| Oil leak | `oil_level`, gauge contact; telemetry history | No dedicated leak/depletion-rate result exists. A decline does not establish leakage. Units remain source-defined. |
| Pressure / DGA | No canonical source field/resource | Explicitly unavailable. No pressure/gas values or thresholds generated. |
| Thermal | Backend model, residual, component readiness/units and history | Residual is displayed only when readiness and observed/model units agree; no inferred headroom. |
| Overload | Backend `loading_percent`, reason codes and asset nameplate metadata | No browser rating division, overload-duration model or invented capacity. |
| Maintenance | Health/anomaly/recommendation metadata; maintenance records | Unreleased risk/confidence remain unavailable. |
| RUL / energy | Existing `/{id}/rul`, `/rul/projection`, `/energy?window=1h&anchor=latest` | Synthetic scenario labelled; no lifetime claim. Missing loss/efficiency remains null. |
| System health | `/api/v1/ingest/mqtt/status` | Broker connection/PUBACK does not prove a per-snapshot SQL receipt. |

All asset paths above are under `/api/v1/transformers`. Charts use actual bounded
`/{id}/telemetry` and `/analytics` responses. Gaps/nulls/unit mismatches break
lines; missing observations are never zero-filled. No backend SSE/WebSocket
route is supplied, so the UI uses bounded polling.

Source kind, lineage, units, verification, measurement and analytics times,
configuration and bundle identity remain visible. Display times use the browser's
local timezone (the reviewed machine uses IST); ISO source times remain in time
attributes/tooltips and API evidence. Replay event time remains historical.
The10-second staleness threshold is a demo configuration, not a universal limit.
Current simulator event clocks can be historical even while transport updates.

## Verification

```powershell
npm test
npm run build
npm run lint
```

The existing Vitest/jsdom runner now includes console behavior tests. Controlled
fixtures are imported only by tests. Live browser evidence is in `screenshots/`:
`overview.png`, `transformer-detail.png`, `mobile-detail.png`, `api-outage.png`
and `live-verification.json`. See [CONSOLE_REPORT.md](CONSOLE_REPORT.md) for actual
results and intermediate failures. Build success alone is not integration proof.
`node scripts/verify-console.mjs` is the exercised local browser verification;
it uses the already available Playwright-core installation in
`$env:TEMP/h06-browser` and installed Edge. On another machine supply an equivalent
Playwright/browser setup before running it; this helper is not a runtime dependency.
It interrupts browser requests only, leaving services and data untouched.

For current ten-asset browser verification use `node scripts/verify-ten.mjs`.
It reads the authoritative shared roster and the running backend, saves both
five-card pages plus detail under `screenshots/operational-ten/`, and verifies
TX10/TX01 isolation and actual telemetry advancement. The older verify-console
script and screenshots remain historical 93-asset evidence, not current acceptance.
