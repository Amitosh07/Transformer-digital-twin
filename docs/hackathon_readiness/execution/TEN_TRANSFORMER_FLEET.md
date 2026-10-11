# Ten named operational transformers - 10 October 2026

Implemented locally on `develop`, baseline `e0c69014d4922feec7aabf5c85cb33e130f7c11e`.
The initial working tree was clean. No commit, push, merge, migration, historical
identity remapping, volume removal, image build or prune was performed.

## Population diagnosis and ownership

Read-only PostgreSQL inspection found 93 registered identities: 75 from three
H07 runs (`H07-dfb1b1-*`, `H07-b41b39-*`, `H07-1ea791-*`, 25 each), plus 18 H06
simulation, replay, arithmetic, rollback and strict-recovery identities.
`demo_portfolio.py` intentionally allocated a fresh UUID run prefix; each run
registered new assets and extended `analytics-policy.json`. The previous default
`demo_runtime.py setup` registered every policy asset. Registry reads counted all
rows and sorted lexically; the console fetched every page and used 12 cards/page.
The dormant educational `frontend/src/data/assets.ts` has three different assets;
neither it nor `scadaSimulation.ts` supplies the operational console. The actual
pre-change running source generated only H06-SIM-05, not all 93 registry rows.

The authoritative roster is now
[operational-fleet.json](../../../simulator/config/operational-fleet.json).
It owns ordered IDs, unit IDs 1-10, independent RNG seeds 42-51, five-second
cadence, the existing declared fictional 30 kVA / 400 V LV configuration, and
the existing H05 power-integration source policy. Those are synthetic parameters,
not verified physical nameplates. No ten-ID list is embedded in React or copied
into each source/bridge configuration.

Backend `OPERATIONAL_FLEET_FILE` scopes the default SQL registry count/query to
that ordered roster using a CASE ordering expression. `scope=all` retains the
complete historical registry; individual old lookup/history resources remain
available. In deployments without a fleet file, existing all-registry behavior
is preserved. Invalid configured rosters fail closed rather than falling back.
No ORM/schema/migration change was needed; all requested IDs already fit the
128-character backend and 64-byte Modbus constraints and MQTT topic rules.

There are now **10 active** and **103 total registered** assets: the original 93
were retained and the ten new canonical identities were added. No historical
telemetry was assigned to a new ID. No identity mapping is justified or necessary:
the new fictional streams start their own histories, analytics, receipts and
checkpoints. All old associations retain their original provenance.

## Actual page composition

| Page 1 | Page 2 |
|---|---|
| KA-BLR-KOR-TX01 | KA-BLR-HSR-TX06 |
| KA-BLR-KOR-TX02 | KA-BLR-HSR-TX07 |
| KA-BLR-KOR-TX03 | KA-BLR-HSR-TX08 |
| KA-BLR-KOR-TX04 | KA-BLR-BTM-TX09 |
| KA-BLR-HSR-TX05 | KA-BLR-BTM-TX10 |

The unfiltered overview has exactly five cards on each page, full IDs, disjoint
sets, `Page 1 of 2` / `Page 2 of 2`, and disabled Previous/Next at the boundaries.
Filtering can deliberately reduce results. Refresh clamps the displayed page;
an identity removed from the active registry stops supplying detail data.
Selection and return-to-overview work from either page. React derives ordering
from the backend; it does not hide 83 independently simulated assets.

## Runtime and safe startup

Normal base Compose now uses `operational-server.json` and
`operational-bridge.json`, which expand the shared roster through the existing
Scheduler, read-only FC04 server, bridge, QoS1 publisher and durable spool.
Before opening FC04, source startup idempotently registers the exact fictional
configuration. Existing conflicting configurations abort startup; they are not
patched or overwritten. Default `simulator seed` registers the roster only,
without fabricated pre-roll/history. Default `simulator stream` polls this fleet's
Modbus bridge. Explicit `--transformer-id` preserves legacy single-asset commands.
The old 25-asset wrapper refuses normal operation unless deliberately invoked
with `--legacy-h06`; historical rehearsal tooling is retained separately.

Each source session starts at current UTC with the same stable IDs/seeds. Sequence
and synthetic meter counters restart explicitly; timestamps are new identities,
old observations are not overwritten, and existing gap/reset handling applies.
Restart source **and bridge together** so an old poller's sequence watermark is
not mistaken for a continuing source session. Backend analytics/checkpoints stay
durable and restore through the existing H01/H02 commit/install protocol.

This machine had only about 3 GiB free on C:. Existing backend/source/bridge
containers were stopped and **retained**, including their logs and writable
layers. No rebuild or container deletion was needed. The tested
[existing-runtime Compose adapter](../../../docker-compose.operational-existing.yml)
starts three replacement workers using the already built H06 images, read-only
current source at its normal installed import paths, the existing Docker network,
and the same external `bridge_spool` volume. PostgreSQL, broker and frontend
containers/volumes remain the original H06 ones. Only one backend ML owner runs.
The current frontend bundle was copied into the existing nginx container; the
underlying original image and older static assets remain retained.

Current loopback ports: PostgreSQL 55433, MQTT 51885, API 8001, frontend 5173,
Modbus 1502. Images remain the H06 images; ML is the actual H01 package with
`DEMO_UNVERIFIED_CONFIG`, not a stub. No operational risk/life validation claim
is made. The fleet has no invented lifetime scenario or physical loss inputs;
operational RUL/risk/loss/efficiency remain unavailable as appropriate, while
health, anomaly, thermal, maintenance and simulated consumption use existing code.

PowerShell, repository root, for **this preserved existing runtime**:

```powershell
# Existing db/mqtt/frontend must be running; never start the retained old workers.
docker compose -f docker-compose.operational-existing.yml --profile primary config --quiet
docker compose -f docker-compose.operational-existing.yml --profile primary up --no-build -d
docker compose -f docker-compose.operational-existing.yml --profile primary ps
Invoke-RestMethod http://127.0.0.1:8001/health/ready
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers?limit=5'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers?limit=5&offset=5'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers?scope=all&limit=1'
python simulator/scripts/demo_runtime.py check
```

Open http://127.0.0.1:5173. The check uses the API, so it needs only Python's
standard library. Default source startup already performs registration.
For manual repeated registration in the tested installed container:

```powershell
docker exec transformer-operational-ten-modbus-simulator-1 simulator seed --http-url http://backend:8000
```

For the shell wrappers on this machine, set `COMPOSE_FILE` to
`docker-compose.operational-existing.yml` and `COMPOSE_PROJECT_NAME` to
`transformer-operational-ten` before using `demo_setup.sh` / `demo_primary.sh`.
The existing-runtime adapter requires Compose supporting `!reset` / `!override`
(tested 5.3.1), the existing H06 network/volume and Python 3.12 images. Environment
variables in that file support other existing image/network/volume names.
Do not point it at a different operator database or start old and new ML workers
simultaneously. Fresh installations use the base Compose build with these same
roster references; that additional clean build was **not run** in this task.

Native approved simulator installations can set `SIMULATOR_CONFIG_DIR` to the
absolute repository `simulator/config` directory, then use:

```powershell
simulator modbus-server --config simulator/config/operational-server-native.json
# In a second terminal:
simulator stream --fleet-bridge-config simulator/config/operational-bridge-native.json
```

Native backend configuration must set `OPERATIONAL_FLEET_FILE` to the same
manifest (example supplied); do not overwrite an existing .env. Native commands
are documented interfaces; this task's live proof used the containers.

## Actual validation and evidence

**PASS (exit 0):**

- Backend: `python -m pytest tests/read_api/test_operational_fleet.py tests/read_api/test_transformers.py tests/test_telemetry_contract.py tests/test_transformer_schemas.py tests/test_h02_transactional_adapter.py -q`: **170 passed**. PostgreSQL fixture used admin database `postgres`, created/migrated a unique `transformer_test_*` database, then removed only that new test database. No test sessions used the preserved `transformer` demo database. Existing deprecation warnings retained.
- Simulator final selection: `python -m pytest tests/test_operational_fleet.py tests/test_schema.py tests/test_modbus_h03.py tests/test_delivery_h03.py tests/test_h07_concurrent_spool.py tests/test_cli_h03.py tests/test_replay_h03.py -q`: **47 passed**. Includes actual loopback FC04, frozen H00 telemetry-schema validation of all ten decoded bodies, deterministic generation, advancing values/times, independent fault contacts, idempotent registration, conflicting configuration rejection, receipt/spool and replay regressions.
- Frontend: `npm test`: **50 passed** after the final registry-removal regression. `npm run build` and `npm run lint` exit 0; lint retains existing warnings in legacy components/polling/thermal exports.
- Compose base and existing-runtime configuration validation exited 0. No image builds performed.
- Repeated real `simulator seed` twice: exit 0, active IDs remain ten and all-registry total 103. No additional history seeded.
- `python simulator/scripts/demo_runtime.py check`: all ten latest observations, persisted analytics and matching committed receipts, exit 0.
- `python simulator/scripts/verify_operational_fleet.py`: [first live trace](evidence/operational-ten/live.json). **20 actual FC04 snapshots**, two changing observations per asset; each exact snapshot/hash has one committed receipt and one telemetry/analytics pair; ten independent checkpoint rows. RUL/energy API responses saved.
- Corrected `python simulator/scripts/verify_operational_fleet.py --identity-test` at the empty-spool/stopped-source barrier: [SQL evidence](evidence/operational-ten/retry.json). Exact retry HTTP **200**, `EXACT_RETRY`, `forward_state_advanced=false`; changed trip contact HTTP **409**. All ten accepted telemetry/analytics/alert/maintenance counts and checkpoint content hashes unchanged.
- Source/bridge and backend restart with the same configurations: [after-restart trace](evidence/operational-ten/after-restart.json), **20 more real correlated snapshots**, stable ten IDs, new event times, durable previous history and checkpoints, one pair per snapshot.
- `node scripts/verify-ten.mjs` from frontend: [actual browser evidence](../../../frontend/screenshots/operational-ten/browser.json). Running nginx/API, two five-card pages and boundary controls, TX10/TX01 isolation, values matching supplied API responses and actual live timestamp advancement. Screenshots: [page 1](../../../frontend/screenshots/operational-ten/page1.png), [page 2](../../../frontend/screenshots/operational-ten/page2.png), [detail](../../../frontend/screenshots/operational-ten/detail.png). No browser JS errors. These are real responses, not UI fixtures.
- Five actual `python -m json.tool` checks, changed Python AST parsing, touched documentation-link resolution, both Compose configurations and `git diff --check` passed. Final fleet module/CLI help check also passed (4 focused tests).

Verification reused existing dependency directories because system Python lacked
pytest. Python commands set `PYTHONPATH` to the existing H02/H03 verification
site-packages; simulator tests also used the source package directory. Browser
verification reused installed Edge and the existing TEMP/h06-browser Playwright
setup. These test-only paths are **not** backend container runtime dependencies.
The full transcript commands are reflected by the test modules/scripts above;
no full earlier-phase suite, portfolio soak or data-generating replay was run.

**Intermediate failures, corrected:** first PostgreSQL command rejected by
automatic review because its URL named the demo database; after inspecting the
fixture it was safely rerun with `postgres` administration and unique test DBs.
First simulator command named nonexistent test modules; actual filenames were
used. Its legacy CLI test then needed explicit `--transformer-id TX-001` under
the intentionally changed fleet default; its assertions were retained. The first
normal check assumed an absent telemetry `payload_hash` response field; it now
compares the actual acquisition snapshot ID. The first ad-hoc retry assertion
guessed 201; the actual documented duplicate result is 200 / EXACT_RETRY / no
advance, and the corrected identity test passed. A Windows text-encoding error
in the edited console file was corrected; build/tests/browser were rerun.

**NOT RUN:** full prior suites, new broker/database outage experiments, 25-asset
load/soak and clean image rebuilds. Existing H06 outage evidence remains historical
baseline; this task does not claim it was newly repeated. H07's failed/incomplete
25-asset acceptance is not converted into a pass by reducing the operational fleet.

## Preservation and remaining limitations

Before the runtime handover, the existing preservation helper created readable
consistent SQLite backups plus a PostgreSQL custom archive under
`D:/TransformerDigitalTwin-H07/20261010-operational-ten/`.
Archive `20261010T111538Z-before-ten.dump` is 5,158,815 bytes;
`pg_restore --list` succeeded and contains telemetry table data. SQLite integrity
checks passed. [Pre-change receipt/spool reconciliation](evidence/h07/20261010-diagnosis/20261010T111534Z-reconciliation.json)
shows primary/original/90-second spools empty, five original primary trace IDs
committed exactly once, and the separate stopped H07-1ea791 spool with **136**
entries, **16** committed awaiting checks. Those 136 entries remain under their
original IDs; this task did not drain/relabel/delete them. The new bridge reuses
the original primary spool and its counters/watermarks; cumulative counters
include previous H06 work and are not a fresh ten-asset measurement.

Initial C: free bytes were 3,195,777,024; after-restart check finished with
3,111,063,552 bytes free. D: stayed above 178 GB free. The bounded live verifier
uses a **2.75 GiB** C: guard which stops only new source acquisition if reached,
retaining delivery/data. This is a local verification safety policy, not a
performance claim or continuous background monitor. Disk headroom remains low;
no 30-minute capacity/latency acceptance is claimed. Before extended operation,
provide more C: capacity without deleting project/queue/database state.

The final SQL snapshot at 11:46 UTC recorded 284-286 observations **and the same
number of analytics rows for each of the ten IDs**, with no duplicate asset/time
rows. [Final state](evidence/operational-ten/final-state.json) records the complete
per-asset counts, health, MQTT diagnostics, unchanged baseline commit, retained
containers and disk values (C: 3,061,555,200 bytes free, database 207,477,783 bytes).
Differences of one or two rows during ongoing processing are not asserted to be
loss; this is a current-state snapshot, not a completed soak reconciliation.

A separate local PowerShell disk guard now monitors C:/D: every 30 seconds and
appends small diagnostic records on D:. It pauses **only the operational source**
if C: falls below 2.75 GiB, leaves receipt delivery running, and never deletes
anything or automatically resumes generation. Its normal branch was actually
tested with `-Once`; the low-space branch was not deliberately triggered.
[Guard process/configuration](evidence/operational-ten/disk-guard.json) records
PID 13296 and the D: log path. This is an ordinary local runtime helper, not a
cloud automation or a storage/performance acceptance result. After capacity is
restored, restart source/bridge together and restart the guard if it exited.
To reproduce the safety helper (avoid starting duplicate guards):

```powershell
pwsh -NoProfile -File simulator/scripts/guard_operational_disk.ps1 -LogPath D:/TransformerDigitalTwin-H07/20261010-operational-ten/disk-guard.jsonl
```

Current safe handover: original DB/broker/frontend running; replacement backend,
ten-asset Modbus source and bridge running; old H06 backend/source/bridge stopped
and retained; H07 load/recovery containers stopped and retained. Normal pending
spool depth fluctuates while active records await their real SQL receipt. It was
zero at the retry barrier; no pending record was manually removed.

## Changed paths and reasons

- `simulator/config/operational-fleet.json`: single ordered roster and explicit fictional configuration/source policy.
- `simulator/config/operational-server.json`, `operational-server-native.json`, `operational-bridge.json`, `operational-bridge-native.json`: container/native endpoint wrappers referencing that roster, not copies of IDs.
- `simulator/simulator/fleet.py`: validated expansion, live UTC start, explicit configuration-directory support and non-overwriting idempotent registration.
- `simulator/simulator/modbus_server.py`, `modbus_bridge.py`: load roster wrappers through existing server/bridge; server registers before FC04 availability.
- `simulator/simulator/cli.py`: default seed/stream target fleet; explicit legacy single-asset mode retained.
- `simulator/scripts/demo_runtime.py`: default setup/check target fleet; deliberate legacy H06/25 switches; no automatic old-policy bulk registration/pre-roll.
- `simulator/scripts/verify_operational_fleet.py`: bounded real pipeline/receipt/SQL/retry proof, no reset or fresh test telemetry injection.
- `simulator/scripts/guard_operational_disk.ps1`: local storage safety; pauses acquisition only, keeps every pending message and persisted record.
- `simulator/tests/test_operational_fleet.py`, `test_cli_h03.py`: roster, schema, generation, isolation, registration and backward-compatible explicit CLI regressions.
- `backend/app/core/operational_fleet.py`, `core/config.py`: active roster loading and environment configuration.
- `backend/app/repositories/transformer_repo.py`, `services/query_service.py`, `api/v1/transformers.py`: active SQL count/order/pagination plus explicit all-registry access.
- `backend/app/services/analytics_resources.py`: reuse existing H05 power calculator with the fleet's explicit synthetic-source policy; no algorithm changes.
- `backend/.env.example`, `backend/docs/api.md`: native configuration and registry scope documentation.
- `backend/tests/read_api/test_operational_fleet.py`: actual PostgreSQL active pagination and preserved legacy lookup, ID/schema validity and fail-closed config tests.
- `docker-compose.yml`: normal runtime roster mount and fleet source/bridge commands.
- `docker-compose.operational-existing.yml`: reuse preserved running database/broker/volume and old images without deleting containers/building images.
- `frontend/src/components/console/MonitoringConsole.tsx`: five-card pages, active labels, exact indicator, valid removed-asset selection; API remains authoritative.
- `frontend/tests/console.test.tsx`: exact ordered disjoint pages, controls, detail return, refresh clamping and removed-selection safety.
- `frontend/scripts/verify-ten.mjs`, `frontend/screenshots/operational-ten/{page1.png,page2.png,detail.png,browser.json}`: real browser checks/screenshots.
- `frontend/README.md`, `simulator/H03_RUNBOOK.md`, this report: current usage and truthful limits; dated previous phase evidence preserved.
- `docs/hackathon_readiness/execution/evidence/operational-ten/{live.json,after-restart.json,retry.json,final-state.json,disk-guard.json}` and the dated reconciliation JSON linked above: actual runtime evidence.

Frozen H00 artifacts, ML algorithms/weights, database models/migrations, CSV fields,
old histories, pending spool payloads and all earlier execution reports are unchanged.
