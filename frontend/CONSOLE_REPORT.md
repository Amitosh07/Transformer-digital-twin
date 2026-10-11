# Industrial operations console — execution report

Verified 10 October 2026, IST. Branch `develop`; prior dirty H00–H07 changes
preserved. This is a frontend redesign, not a new phase implementation or a
capacity acceptance rerun. No backend, ML, simulator, Docker/Compose, schema,
volume, spool or prior execution report was modified by this task. No commit,
push or merge. The current dev server is on loopback 5174; existing Docker UI
on 5173 retains its earlier image and was not rebuilt.

## Changes

- `src/App.tsx`
- `src/api/client.ts`
- `src/hooks/useConsoleData.ts`
- `src/components/console/MonitoringConsole.tsx`
- `src/components/console/TelemetryPanels.tsx`
- `src/components/console/TrendCharts.tsx`
- `src/components/console/presentation.ts`
- `src/components/console/console.css`
- `tests/console.test.tsx`
- `vite.config.ts`
- `index.html`
- `.env.example`
- `README.md`
- `frontend_README.md`
- `scripts/verify-console.mjs`
- `CONSOLE_REPORT.md`
- `screenshots/overview.png`
- `screenshots/transformer-detail.png`
- `screenshots/mobile-detail.png`
- `screenshots/api-outage.png`
- `screenshots/live-verification.json`

Generated build files under ignored `dist/` and existing compiler caches are
normal verification outputs. No dependency or lockfile change was required.
Historical presentation components/data were retained but are not imported by
the new App entry point. `frontend_README.md` has a current-document notice;
previous H04/H06/H07 reports remain historical evidence.

## Design and API reuse

Default view is the operational asset overview, not a landing page. Navy sidebar,
compact header, cool grey surfaces and an equipment-centred SVG composition
follow the supplied reference. Drawn equipment is illustrative; all changing
values are ordinary typed React elements. There are six dedicated feature panels,
recent event table, selectable actual telemetry trends, configuration/evidence
views, system diagnostics and existing RUL/energy/health cards.

Existing Zod API parsing, errors, timeout, usePolling, thermal readiness,
forecast-release gate and nullable resource cards were reused. Lifecycle responses
now also validate asset identity. A failed request retains that asset's previous
data and last-success timestamp, with visible error and staleness. Asset switching
clears obsolete selected data before later responses can render. No failed or
missing response is converted to zero or normal/healthy status.

Actual resources confirmed by current `/openapi.json` (HTTP200):

| Section | Actual existing paths under `/api/v1` |
|---|---|
| All registry assets / selector | `/transformers?limit=50&offset=...` |
| Visible overview cards / equipment / six feature inputs | `/transformers/{id}/latest` |
| Actual bounded trend / model history | `/transformers/{id}/telemetry`, `/analytics` with aware from/to, anchor=latest, newest300 rows |
| Recent events / maintenance | `/transformers/{id}/alerts`, `/maintenance`, bounded24-hour event window and final30-item ascending offset page |
| Scenario RUL / actual projection | `/transformers/{id}/rul`, `/rul/projection` |
| Bounded event-time energy | `/transformers/{id}/energy?window=1h&anchor=latest` |
| Transport diagnostics | `/ingest/mqtt/status` |

There is no supported backend SSE/WebSocket route, so bounded polling is used.
Overview requests only the visible12 cards with at most3 concurrent latest calls;
15s between completed rounds. Registry pages are fetched sequentially every60s,
including all 93 current rows. Status/alarm filters explicitly operate on the
visible page; ID/name search covers the complete fetched registry. No portfolio
history fan-out. Selected latest runs every configured2–5s (default3); active
history/events15s, maintenance RUL15s, projection/energy30s. Event-time refs
avoid restarting energy polling whenever a latest event changes. Unmount/key
changes abort requests and cancel timers. Timeout remains10s.

All six feature areas are represented, with these evidence limits:

- Oil level/gauge contacts and selectable level history exist; no dedicated
  leak result or depletion-rate field is supplied. A decrease is not a leak diagnosis.
- Pressure and DGA have no canonical fields/resources: explicitly unavailable.
- Phase voltage/current, protection contacts, anomalies and persisted alerts exist;
  temperature contacts/anomalies are not confirmed short circuits.
- Model temperature/residual is shown only under component readiness and matching
  source/model units. WTI is displayed as a source indicator, not winding °C.
  Thermal headroom is withheld without verified limits.
- Loading is the backend `loading_percent`, never a frontend rating calculation.
  No duration/capacity estimate is invented.
- Health, recommendations, trip latch, reason evidence, RUL/energy are backend
  results. Operational risk/confidence remain behind the established release gate.
  Synthetic RUL is labelled scenario time, not equipment lifespan. Null loss/
  efficiency stays unavailable. Source field verification is never inferred.

Source kind/lineage, measurement/analytics timestamps, last-success poll, map,
sequence, snapshot, configuration and bundle evidence remain visible. Times are
localized with timezone; original ISO timestamps remain available as attributes/
tooltips and captured JSON. The10s staleness default is labelled as a demo policy.
Historical simulated source clocks remain stale despite active broker traffic.
No excluded raw voltage columns were introduced.

## Actual verification

| Check | Result / evidence |
|---|---|
| `npm test` from frontend | PASS:47 tests,6 files, including9 new console cases; original38 also pass. |
| `npm run build` | PASS: final TypeScript/Vite build,2005 modules; JS372.84kB, gzip112.95kB. |
| `npm run lint` | PASS exit0;16 existing warnings in unchanged historical components/hooks. No new console warnings. |
| `node scripts/verify-console.mjs` | PASS against actual Vite/FastAPI/PostgreSQL-backed responses; Edge 155.0.4283.45. |
| Actual registry pages | PASS:93 distinct assets; portfolio asset25 appears beyond first page. |
| Two-asset isolation | PASS: actual selected measurements matched returned current/unit; distinct snapshot identities; switching never reused old asset's readings. |
| Live polling | PASS: actual primary snapshot advanced between observed successful responses. Event clock remains historical/stale. |
| Outage / recovery | PASS: aborting real browser requests produced API error and preserved last-success; removing network interruption + retry recovered. No service stopped or fake response installed. |
| RUL / energy | PASS: actual HTTP200 resource responses rendered; no frontend calculation fallback. |
| Visual desktop/mobile | PASS:1600px desktop and390px mobile, no document horizontal overflow; saved PNGs inspected against supplied reference. |
| Race, null/zero/unknown units, paging, concurrency, chart gaps | PASS: focused console tests plus existing polling/resources/client tests. |

The native in-app automation entry point was unavailable (`failed to write kernel
assets`); the existing installed Edge/Playwright helper was used instead, with
real HTTP responses. This is browser integration evidence, not a new ingestion,
SQL-transaction, Modbus or25-asset throughput proof. Those tests were not rerun.

Intermediate failures preserved in the work log: one patch combined incompatible
operations and was rejected before changes; npm test was once invoked from root
without a package.json; npm flags were stripped by the Windows invocation, so the
explicit Node/Vite command replaced it. An index metadata write initially used
Windows encoding, causing a Vite invalid-UTF8 build failure; saving UTF8 corrected
it and the final build passed. The first repair used a wrong cwd-relative path
and did not modify a file. No tests/assertions were removed to obtain passing results.

## Concrete actual response / display

- `H06-SIM-05`: current L1 **18.21 A**, source **SIMULATED**, event `2026-10-09T05:48:35Z`, snapshot `b5a46317d86f9a264dc66180f0c567c6e704e733350c2821590b4f6bce311e72`. Browser text matched the supplied value/unit and correct selected asset.
- `H07-b41b39-02`: current L1 **25.74 A**, source **SIMULATED**, event `2026-10-10T07:40:12.245258Z`, snapshot `565eeeef82445e86d080207d49a7e65ed94ee2ec0849daace16fbd72bdb253e7`. Browser text matched the supplied value/unit and correct selected asset.

Final live verification recorded `2026-10-10T09:50:51.814Z` UTC (IST display). The runner explicitly waited up to40s for the selected DOM snapshot to differ from the prior identity; both saved API identities differ. One earlier preliminary capture had successful polls but no identity advancement, so it was not used as final live-update proof. The strengthened check passed.

[Live verification JSON](screenshots/live-verification.json) preserves actual
responses, event times, source metadata, DOM, outage and snapshot advancement.
This file contains test evidence only; the runtime never imports it.

## Screenshots and reproducibility

- [Overview](screenshots/overview.png): actual registry search returns 25 configured portfolio assets, first page of 12; stale/source labels remain visible.
- [Selected transformer](screenshots/transformer-detail.png): actual measurements around SVG, six feature panels,300-of 721 bounded trend and real recent events.
- [Mobile](screenshots/mobile-detail.png):390px responsive composition.
- [API outage](screenshots/api-outage.png): retained data explicitly errored/stale.

See [README.md](README.md) for the exercised PowerShell command and existing
Playwright/browser prerequisites. Current source is available at
`http://127.0.0.1:5174`; no container rebuild was used to avoid disk growth.

## Remaining limitations

Pressure/DGA/leak detector and verified thermal headroom have no supported
pipeline output. Real source evidence/fitted artifacts and operational lifetime
risk eligibility remain incomplete as recorded by earlier phases. Portfolio
latency/capacity and the blocked full 30-minute H07 run are not improved or
accepted by this frontend work. Offset pages can shift during concurrent writes;
trends and event lists are explicitly bounded/partial. Browser interruption
proved UI failure handling, not a new backend outage recovery gate. The old
Docker frontend image remains unchanged; publishing this source through that
image is a separate local runtime action, not claimed here.
