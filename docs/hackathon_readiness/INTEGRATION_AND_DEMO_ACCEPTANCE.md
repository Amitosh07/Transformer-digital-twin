# Integrated acceptance and judging demonstration

This is an executable **future acceptance specification**, not a passed test report. Baseline `develop` 71c1b27 has component tests and routes but does not yet run this entire suite. H06 creates/verifies named new scripts/configs/commands; H07 records actual results. Exact gap ownership and order: [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md). All live equipment is optional, authorized and read-only.

## Evidence and mode rules

Record commit, software versions, hardware, configuration/bundle/map versions, command/exit code, expected versus actual output and asset/event/receipt/hash correlation. Report PASS/FAIL/BLOCKED separately, including skipped tests. Artifacts unavailable→explicit demo-unverified runtime, never trained/validated claim. Source kinds SIMULATED/REPLAYED/LIVE, origin, units and freshness survive every boundary. A synthetic replay is REPLAYED with SIMULATED origin; it is not a live device. operational RUL/risk may be null while synthetic RUL genuinely computes time-to-defined-scenario-endpoint.

## Acceptance suite

| Case | Procedure / oracle | Required observation / evidence |
|---|---|---|
| A01 clean setup (F02/F03/F15) | New isolated environment, install/build documented runtime, migrate empty disposable DB | All required services ready; actual Python ML package installed; original verified or explicit demo-unverified bundle; no hidden existing .env/data/node_modules dependency |
| A02 source time and validation (F09/F10/F11) | Fixed seed/startUTC/config; send valid, naive/unknown time, NaN, malformed alarm and missing fields | Aware valid event retained; invalid rejected with reason; unknown source timezone staged/explicit assumption; missing null not zero; boolean protection inputs normalize to integer0/1; fictional nameplates labelled |
| A03 actual Modbus (F06) | Independent FC04 client reads defined unit/map; compare snapshot/time/sequence with bridge output | Genuine request/response, scale/endian/quality verified; no control writes; same canonical values appear in SQL/API/DOM |
| A04 IoT (F06/F12) | Modbus bridge publish QoS1 on asset topic; test mismatch, torn snapshot, retained stale message and broker outage | Topic id checked; torn read retried/skipped; stale not refreshed; receipt distinguishes PUBACK versus SQL; bounded durable spool and diagnostics |
| A05 persistence/idempotence (F12/F14) | Exact retry, changed same-key trip0→1, SQL failure, then retry | One accepted row/effect; changed payload409/conflict quarantine; receipt only after commit; deterministic hash excludes its own snapshot_id and backend receipt time; state/alerts/energy not double advanced |
| A06 ML state and metadata (F04/F13/F18) | Real Python client, ≥1h event history, rollback and backend restart | Component units/readiness/coverage/extended reasons persist; state restored or visibly reinitialized safely; risk null without release evidence; no late mutation |
| A07 actual API dashboard (F01/F08/F19) | Compare selected asset/latest/history/alerts/maintenance JSON to DOM; switch while delayed response; fail API | Same values and timestamps/reasons, no local substitute formulas/mock fallback; loading/no-data/error/stale/unknown units shown; unsupported claims removed |
| A08 RUL required (F05) | Synthetic D=.2/end1/g=.01/hour with enough horizon; zero/end/missing cases; real incomplete config | 80h scenario crossing,0 at threshold,null no crossing/insufficient; scenario bounds not confidence; method/config/assumptions; real value stays null with required inputs |
| A09 energy required (F07) | Covered10kW2h; ramp0→10kW1h; counter100→110 then reset→2; irregular gap and unknown units | 20kWh/5kWh/10kWh within numerical tolerance; reset excludes jump, duplicates0; coverage/method/source shown; unknown units no numeric kWh |
| A10 conservation/loss (F07/F09) | Eligible synthetic loss-config comparator at same delivered service; repeat missing loss/side inputs | Declared P0+PrK² model/assumptions, simulated opportunity only; missing loss/efficiency null; eligible fictional10kW output/1kW loss yields approximately90.9091 percent; safe evidence-triggered advice; no actual savings/compliance claim |
| A11 abnormal chain (F10) | Pre-roll history, normal→rated overload→thermal divergence→alarm→trip→recovery | Measurements physically coupled, model lag/readiness honored; persisted reasons/alerts/maintenance consistent with supported existing rules; trip override visible; no promised48h warning |
| A12 history and source modes (F11/F13) | Canonical replay same trace at1×/20×, separately registered replay asset id with origin_transformer_id/replay_run_id and explicit fallback | Event-time energy/degradation unchanged; original history/date labelled; no timestamp collision/live state contamination; HTTP fallback says Modbus unavailable |
| A13 asset configuration (F09) | Register/PATCH all declared nameplate fields plus absent/UNVERIFIED rating | Registry round-trip; loading/loss/thermal eligibility gated; same-side units; no fabricated standards limits |
| A14 missing/stale/disconnected | Remove register quality, stop asset, stop broker/DB/API, restart | Missing contacts remain unknown; last timestamp frozen, stale visible; no healthy status solely from absent data; checkpoint/spool recover without doubled effects |
| A15 portfolio (F16) | 25 assets5s30min; one asset fault, rapid selection, independent restart | Isolated state/energy/RUL/alerts; measured proposedp95<10s at tested hardware; report counts/gaps/drops/memory/actual capacity; explicitly25 simulated |
| A16 fresh teammate rehearsal (F15/F20) | Teammate follows runbook without undocumented steps | Primary protocol demonstration and fallback executable; all output labels/claims honest; evidence linked for every P0/P1 |

A09 fixtures configure permissible covered intervals explicitly; the default5s cadence gap limit must not blindly accept a2h hole. Counter totals across gaps require independent continuity proof. Accelerated scenario timelines retain event time; latency measurements use receipt/commit/browser clocks and declare timing uncertainty, not historical event date subtraction.

## Commands that exist in the baseline

From repo root (venv with relevant dependencies):

```bash
git branch --show-current
git rev-parse HEAD
git status --short
python -m unittest ml.tests.test_pipeline ml.tests.test_prediction ml.tests.test_thermal_twin ml.tests.test_anomaly ml.tests.test_health_index ml.tests.test_maintenance
python -m unittest ml.tests.test_release
```

The last command currently needs absent original release files; its failures/skips are meaningful, not a reason to invent a manifest. Add new H01/H05 module tests by actual module name after implementation.

From `backend/`:

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/test_telemetry_contract.py tests/test_transformer_schemas.py tests/test_analytics_schemas.py tests/ml_client
python -m pytest tests/test_migrations.py tests/ingestion tests/read_api tests/alerts tests/hardening tests/mqtt
```

TEST_DATABASE_URL must point at disposable PostgreSQL with CREATE DATABASE privilege. Existing fixtures create/drop only unique transformer_test_* databases. The provided example URL is local demonstration configuration, never a production target:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://transformer:transformer@127.0.0.1:55433/transformer'
```

Set it in the same shell before the SQL-dependent commands. Real broker tests in `backend/tests/mqtt/test_broker.py` require MQTT_TEST_HOST and MQTT_TEST_PORT (for proposed local Compose,127.0.0.1 and51885). Set these explicitly before the broker test. Most other MQTT tests use FakeClient from `backend/tests/mqtt/conftest.py`; their passes alone do not prove transport. H06 must record actual broker settings. A skipped integration test is not verified.

From `simulator/` and `frontend/` respectively:

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/test_schema.py
simulator --help
simulator stream --help
simulator replay --help
```

```bash
npm ci --ignore-scripts
npm run build
npm run lint
```

Frontend has no baseline test script. H04 adds and reports a focused actual test command; do not claim `npm test` already exists.

Existing root runtime commands (primary configuration must be fixed in H06 first):

```bash
docker compose config
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8001/api/v1/transformers
curl --fail http://127.0.0.1:8001/api/v1/transformers/TX-001/latest
curl --fail 'http://127.0.0.1:8001/api/v1/transformers/TX-001/telemetry?anchor=latest&limit=10'
```

Baseline Compose uses stub, references absent backend/.env and lacks frontend/Modbus services; these commands are not currently a complete demo. Existing backend entrypoint waits for DB then `python -m alembic upgrade head`. Local native server command supported by current app is `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001` from backend, with DATABASE_URL, CORS, MQTT and installed ML set explicitly. H06 must publish a verified native alternative if needed.

## End-to-end commands H03/H06 must create and verify

The following are proposed interfaces, intentionally labelled **not present in the baseline**. H06 must create and run them, then update the final execution runbook if any actual flag/path differs. They are concrete acceptance outputs, not guessed working commands.

```bash
bash simulator/scripts/demo_setup.sh
simulator modbus-server --help
simulator modbus-bridge --help
simulator replay-canonical --help
bash simulator/scripts/demo_primary.sh
python simulator/scripts/demo_probe_modbus.py --config simulator/config/hackathon-single.yaml
bash simulator/scripts/demo_check.sh
bash simulator/scripts/demo_replay.sh
bash simulator/scripts/demo_25.sh
```

Expected implementation: setup writes local missing configs safely and registers declared fictional assets; primary starts actual simulator→bridge→MQTT ingestion, probe independently reads registers and verifies canonical snapshot, check compares receipt/telemetry/analytics/API. Replay registers a separate destination such as TX-001-REPLAY, copies configuration provenance, and sends the approved JSONL through canonical HTTP using the new --transformer-id flag with REPLAYED+origin provenance. It preserves event timestamps and forward-stream rows/state. The dashboard explicitly switches to the replay asset; it does not relabel the original stream. All scripts use real H03 flags and nonzero exit on failure; they do not destructive-reset existing volumes. Root Compose planned service names and defaults: db55433, mqtt51885, backend8001, frontend5173, modbus-simulator1502, modbus-bridge (no external port). Bind published services to127.0.0.1. Exact commands must be validated during H06, not marked working by this document.

Proposed additive API probes after H02/H06 (receipt hash supplied by generated trace):

```bash
curl --fail http://127.0.0.1:8001/api/v1/transformers/TX-001/rul
curl --fail 'http://127.0.0.1:8001/api/v1/transformers/TX-001/energy?window=1h'
# Proposed energy resource reuses existing anchor convention for historical fixtures:
curl --fail 'http://127.0.0.1:8001/api/v1/transformers/TX-001/energy?window=1h&anchor=latest'
```

Historical fixed-date fixtures must use the API's explicit time bounds where supported, or a controlled clock for tests; `window=1h` relative to now must not falsely test an old trace. H00 freezes bounded-energy query semantics, H06 records actual command. No screenshot or expected JSON is a substitute for running these probes.

## Realistic judging script

Prepare: tested laptop/local services, deterministic scenario trace with ≥1h thermal/feature pre-roll and sufficient existing persistence duration, declared fictional assets/config, bundle/map version and known-input analytics fixtures. Pre-roll via accelerated event-time playback, not artificial readiness flags. Rehearse before presenting; keep a recorded protocol trace if network/presentation fails.

1. **0–2min: architecture and source.** Show actual running services and banner SIMULATED, model mode and fictional nameplate. Independent FC04 read shows timestamp/sequence matching bridge/receipt/API/dashboard. State that no college telemetry is assumed.
2. **2–5min: monitoring and abnormal chain.** Switch normal→rated overload→thermal divergence→alarm/trip in the preconfigured accelerated timeline. Show load/thermal residual/readiness, persisted HI/reasons and advisory maintenance; do not promise anomaly persistence quicker than existing model rules. Missing register and stopped bridge visibly stale/unavailable.
3. **5–7min: mandatory RUL.** Show computed synthetic degradation trajectory/threshold and80h known example or active scenario, vary declared future duty to change crossing, show scenario range. Switch to insufficient real-asset example and explain required data. Do not imply oil surrogate is hot spot or scenario accuracy is empirical.
4. **7–9min: energy/conservation.** Display covered power profile/consumption and a reset/gap; verify method and arithmetic. Show equal-service simulated loss comparison if eligible, otherwise explain nullable losses and evidence-triggered advice. No measured savings assertion.
5. **9–11min: portfolio/resilience/fallback.** Select several of25 labelled simulated assets, fault one with neighbors unaffected. Present recorded30min capacity results, not an11min claim of full soak. Stop primary, show labelled replay fallback preserving event dates and energy; Modbus status remains disconnected. End with evidence/limitations and what authorized real acquisition would require.

Longer model persistence and soak are run beforehand; judges see honest historical/accelerated results rather than waiting for hours or receiving fabricated immediate states. Adapt presentation time to actual organizer slot;11min is a team rehearsal estimate only.

## Final checklist and reporting

- [ ] develop baseline and changed files identified; no unauthorized commit/push/main merge.
- [ ] Actual Python ML installed, strict versus demo-unverified mode labelled, forecast gate preserved.
- [ ] Modbus read proof, MQTT/spool/SQL receipt proof and canonical timestamp/hash correlation saved.
- [ ] Migrations and SQL tests actually executed; queue/rollback/restart/conflict diagnostics checked.
- [ ] Browser consumes actual API, all null/unit/source/stale/error states verified.
- [ ] Nameplate unknowns remain explicit; no fake rise/insulation/lifetime parameters.
- [ ] Genuine synthetic RUL and real-source insufficiency displayed; no empirical accuracy invented.
- [ ] Event-time energy/reset/gap arithmetic passes; losses and opportunities qualified.
- [ ] Replay/fallback modes and25-asset isolation/capacity measured truthfully.
- [ ] Fresh setup/current commands and judging script rehearsed by another teammate.
- [ ] Every P0/P1 has closure evidence or explicit FAIL/BLOCKED; remaining external-data limitations listed.

H07 writes actual results under `execution/`; leave this specification as an acceptance contract and do not pre-check boxes. Missing live equipment, raw source semantics, verified thermal/lifetime/loss evidence and original trained artifacts must be disclosed. Complete local software demo is possible without them through explicit simulated methods; these limitations prevent real operational/empirical claims.
