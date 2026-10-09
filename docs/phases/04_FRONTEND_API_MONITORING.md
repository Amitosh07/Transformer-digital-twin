# H04 — Replace local analytics with truthful API monitoring

## AI CODING AGENT PROMPT

You are implementing one authorized phase of the Transformer Digital Twin on `develop`. Inspect the listed files and necessary imports/tests only; do not re-audit the repository. Read the phase prerequisites and the relevant F findings in `../GAP_ANALYSIS.md` (relative to this prompt). Verify the current branch and local changes before editing. Preserve teammate changes; stop on an ownership conflict rather than overwriting them. The planning baseline is develop `71c1b27200b91f3933c52692748935f4a62d63e8`; newer code requires a narrow relevant delta check.

Implement only the work below. Do not commit, push, merge, touch `main`, retrain existing models, rewrite valid thermal/anomaly/HI/maintenance algorithms, change frontend stack, or write to real transformer/protection controls. Do not change excluded canonical fields or turn missing values into zero. Preserve existing tests and honest null operational forecast. New future CLI/API paths below are implementation targets, not claims that they exist today.


### Objective, owner, defects and dependency boundaries

Owner Person 3, frontend. H00 required; H02 live endpoint needed for live proof, H05/H06 for final RUL/energy backend delivery. Closes F01/P0, F08/P1, F19/P2 and portfolio UI half F16/P2. Frontend client/views can start using explicitly labelled H00 test fixtures in parallel with H01–H03. Fixture-only tests do not close integrated F01; live evidence is H06.

Inspect `frontend/src/App.tsx`, `frontend/src/types.ts`, `components/{InteractiveTwinStudio,HealthIndexDial,ThermalResidualChart,PrescriptiveActionCard,ImpactMetrics,Hero,PipelineWalkthrough,FeaturesGrid}.tsx`, `data/`, `frontend/package.json`, existing CSS/components, backend existing latest/history/trends/alerts/maintenance/registry response schemas and H00 addendum. Keep React/Vite, existing charts/canvas styling and component layout; no Streamlit rewrite or gratuitous routing library.

### Exact implementation, outputs and contracts

1. Add typed API module and a small polling hook with configurable VITE_API_BASE_URL. Registry drives asset selection; selected latest, bounded history/trends, alerts and maintenance come from actual REST. Use 2–5s configurable polling; abort superseded asset requests, suppress old responses, dispose timers. Partial request failures are visible and do not replace valid data with fabricated healthy values. Bound history/pages and respect existing API query parameters.
2. Switch monitoring data source from runTwinSimulation/generateTimeSeriesPoints to API responses. Local educational sliders may remain in an explicitly separate simulation sandbox that cannot affect monitoring state; remove dead paths if separation is needlessly complex. Monitoring Health Index/weights/reasons, risk/confidence and maintenance are backend results, never client recomputation. Remove unsupported +48h/-74%/<15ms/100% claims unless actual evidence is supplied and linked.
3. Model every nullable field and actual enums. Render missing as unavailable with reason; empty history as no observations; retain gaps instead of connecting invented samples. Oil level is not automatically %, WTI status is not °C, and source-unit thermal estimates use metadata units/readiness. Keep unknown contact distinct from cleared contact. Show model/bundle state, health coverage, event timestamp and analytics timestamp independently.
4. Display acquisition source_kind/source_name, last receipt/poll, gateway/broker status, expected cadence, stale/disconnected/no-data/error/loading states. At demo5s cadence proposed staleness is10s, configurable. Historical REPLAYED event date is not a current live sensor timestamp; show playback receipt freshness separately. A failed poll cannot refresh last-success. Legacy provenance is UNKNOWN, never LIVE.
5. Add registry/nameplate inspection view showing kVA, HV/LV volts, current and side, Hz, vector group, impedance, cooling, verified rise limits and configuration provenance. Unknown entries show configuration required; no default values injected in UI. Add portfolio list/status counts from registry and independently fetched bounded latest results, not the three hardcoded assets. Avoid 25 parallel unbounded history requests.
6. Implement RUL and energy display against H00 response fixtures now, then wire real resources in H06. RUL shows simulated/conditional/insufficient labels, hours-derived display with declared conversion, scenario/threshold/coverage/bounds and assumptions. Zero RUL differs from unavailable; no-crossing is not infinity. Energy shows P/consumption/load profile, method/source/coverage/gaps/resets and nullable losses/efficiency, recommendations without unmeasured savings. No browser-calculated replacement estimator. Controls may request explicit replay/simulator actions only after their API exists; no real equipment controls.

Expected files: typed client/hooks, API-driven studio/portfolio/cards with minimal existing-component modifications, environment example, focused UI tests, optional test runner dependency/script if none exists. No backend/ML/simulator edits here; no fixture data shipped as hidden live fallback.

### Acceptance and focused tests

Existing commands from `frontend/`: `npm ci --ignore-scripts`, `npm run build`, `npm run lint`. Baseline has no test script: add the smallest appropriate hook/render test setup and document its exact command, then test asset-switch races, null/0 distinction, delayed/failed polling, unknown units, stale cadence, trip/alarm, operational null risk, and RUL/energy labels. Do not claim build alone validates runtime integration.

Use real backend browser proof in H06: API telemetry timestamp, scores and reasons match rendered DOM; changing API asset/data changes dashboard without touching fixtures; backend outage shows unavailable/stale. Existing charts/layout remain usable at desktop/mobile. H04 can report fixture-level implementation ready before H02, but F01 completion requires H06. Never hide a failed real request by loading local synthetic analytics.


### Completion report and stopping point

Report phase ID, changed paths, contract/version changes, actual commands and outcomes (passed/failed/skipped separately), unmet acceptance criteria, remaining inputs, and the exact next dependent phase. Include one concrete input/output example and any regression or integration evidence. Do not claim unavailable infrastructure tests passed. Update the phase execution evidence in `docs/hackathon_readiness/execution/` with a new phase-specific report; do not overwrite audit evidence. Stop after this phase's assigned outputs and focused checks. A blocked gate stays blocked; do not begin another phase or silently substitute stub results.
