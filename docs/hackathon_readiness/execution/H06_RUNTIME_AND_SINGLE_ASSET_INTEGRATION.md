# H06 execution — runtime and single-asset integration

Started: 2026-10-09; continuation: 2026-10-10 (Asia/Calcutta). Branch: `develop`. HEAD before and after:
`29dcfaf5e12ef50446d1106c4994a721dc802476`.

**The container runtime, single-asset path and strict broker-outage recovery gate
have now been demonstrated.** The final identity-scoped recovery runner passed
against actual Mosquitto/PostgreSQL, with durable pending state and unchanged
side effects/checkpoint on HTTP/MQTT retries. Earlier failed attempts are retained
below. H06 is ready for manual review of this evidence; final phase acceptance
still requires agreement on the disclosed thermal/history coverage and remaining
visual failure rehearsal. No H07 scale/soak was performed.

## Established baseline and changes

Read the H06 specification, frozen contract, integration acceptance and roadmap,
H01–H05 reports, H03 runbook, dataschema/mlcontract and the necessary component
interfaces. Prior reviews were accepted. No prior phase was rebuilt, no frozen
contract/fixtures or ML algorithms were changed, and no existing migration was
edited. Envelope remains `1.1.0`; feature/preprocessing/artifact/checkpoint
versions do not change merely because the envelope changed.

See [current runbook](../../../simulator/H06_RUNBOOK.md) for commands/configuration.
The final path inventory is at the end of this report. Existing work was checked
against the pre-edit SHA-256 inventory; only declared H06 paths were modified.
No reset, clean, revert, commit, push, merge or branch switch was performed.

## Runtime and configuration

Six Compose services: PostgreSQL 16 (`127.0.0.1:55433` → 5432), Mosquitto 2
(51885 → 1883), Python backend (8001 → 8000), React/Nginx (5173 → 80), simulator
(1502 → 1502), and the bridge in profile `primary`. Internal communication uses
service DNS. Database/MQTT volumes are retained and the non-root bridge gets a
bounded writable named spool. Registration/pre-roll precede enabling the bridge.
Migrations run through the existing backend entrypoint. Readiness dependencies,
frontend API URL and local CORS are configured. `.env` is optional and existing
local configuration is never overwritten by setup. Existing operator PostgreSQL
on port 5432 was not used or modified.

Backend image builds/install wheels for the actual `transformer-ml-runtime` and
backend packages. It sets `ML_BACKEND=python`, `ML_PYTHON_ENTRYPOINT=ml.pipeline:analyze`
and exactly one Uvicorn worker. The existing runtime lease/candidate adapter is
preserved. The native import from `backend/` resolved to installed
`Python313/Lib/site-packages/ml/__init__.py`, not a repository path workaround.

Mode is explicitly **DEMO_UNVERIFIED_CONFIG**, bundle
`demo_unverified_coded_config_v1`, model identity `DEMO_UNVERIFIED_CONFIG`, feature
and preprocessing `1.0.0`. Authentic fitted artifacts remain unavailable; strict
fitted release stays blocked. Demo success is not evidence of fitted accuracy.
Operational fault risk, prediction confidence and validated forecasts remain
null/gated. Source measurements and configured asset ratings are explicitly
fictional/synthetic; no verified physical nameplate or real lifetime is invented.

The installed approved H05 ML wheel SHA-256 is
`3fe9b2985cbfe91cfbd3932de697413da4e8f6a2d55f6cfcaac9b82a9fbd4006`.
Final simulator wheel 1.0.0 SHA-256 is
`2ae90f07d57e60016795782d544b0f21d081a5c8edc584da63323d26ecb36cb0`.
It was built/installed from a narrow temporary export to preserve prior local
build/egg-info files. Native protocol is pinned `pymodbus==3.6.9`; broker fallback
is actual `amqtt==0.11.3`, not an acknowledgment mock.

## APIs, persistence and transaction integration

- `GET /api/v1/transformers/{id}/rul` reads accepted persisted H05 RUL from
  analytics, with its actual result timestamp/provenance/reasons. It performs no
  new inference. Unknown assets return 404; missing results remain null.
- `GET /api/v1/transformers/{id}/rul/projection` is a separate additive resource
  reading the matching checkpoint's H05 trajectory. H00's RUL object was not
  rewritten to invent a curve field. Curve and RUL timestamps must match by
  instant; otherwise the curve is unavailable.
- `GET /api/v1/transformers/{id}/energy` queries bounded persisted canonical
  rows, plus bounded boundary context, and calls H05's pure calculator. It uses
  existing `from`, `to`, `anchor=latest|now` and `window=1h|6h|24h|7d` semantics,
  configured maximum window and record cap. The UI's 2h choice sends explicit
  event-time bounds. Counter readings are never averaged/summed as consumption.

`ANALYTICS_POLICY_FILE` supplies explicit asset-specific, versioned fictional
RUL/source/counter/sign/gap policies. No missing source policy grants units or
physical eligibility. Main policy is `h06-policy-v1`, fictional asset configuration
`fictional-demo-v1`. RUL configuration is passed through H01's existing additional
configuration interface before checkpoint import/prepare/install. The backend
retains validate → identity check → private candidate → SQL telemetry/analytics/
effects/receipt/checkpoint → commit → install ordering. H02 already has required
JSON persistence, so no H06 migration is needed. Alembic head remains `0004`.

Real integration tests exposed two defects, fixed narrowly: telemetry field
projection inherited an input validator that dereferenced omitted asset identity;
ML failure skipped protection alert evaluation. Protection now persists without
manufactured analytics; maintenance requires actual analytics. Unknown contacts
never clear unresolved protection. Alert/effect persistence failure still rolls
back the entire accepted observation and discards its candidate.

Older focused tests were updated to the already-established H02 contract:
complete sorted asset locks before multi-asset transactions; release fixture
locks in the creating thread before TestClient commits; nullable analytics on
ML failure; atomic rollback on alert repository failure; H02's allowed
`schema_version` field and current aware-timestamp error. Original identity,
null, protection, alert and rollback assertions were preserved or strengthened.

## Simulator, delivery and frontend

Map `fictional-lv-v1`, asset `H06-SIM-05`, unit 1, gateway `H06-DEMO-GW`.
H03's FC04 address, signedness, float/counter/time encoding, units, quality and
sequence-before/after checks are reused. The native server remains loopback;
container bind requires explicit `container_network=true`. No control writes.

Setup creates one-hour event-time pre-roll of 60 observations at an explicitly
declared 60-second cadence, then the source runs at five seconds. Pre-roll is
encoded/decoded through the same register map and lineage as forward polling.
It is not 720 five-second observations and does not prove full thermal/feature
coverage: existing H01 gap/readiness metadata remains visible and reduced.
The fictional RUL/source policies allow a disclosed 90-second interval; no ML
thresholds or warm-up flags are altered. Energy boundary interpolation is
explicitly declared for these fictional instantaneous-power scenarios only.

Bridge polling is two seconds, source cadence five seconds, QoS 1, no retained
telemetry and unique client identity. Semantic snapshots are stable across
ordinary retries. PUBACK does not remove a spool entry; only a matching H02
committed receipt/hash does. HTTP errors/missing receipts retain entries;
conflicts quarantine. Limits are 10,000 records/16 MiB payload and acquisition
backpressure. Replay is separate registered `H06-REPLAY-R1`, run `H06-R1`, with
original event times and `REPLAYED`/simulated-origin lineage. Canonical replay is
an explicit HTTP fallback, not Modbus proof.

Frontend fixes the two H05-identified parsers: replayed synthetic RUL keeps
REPLAYED source; simulated counter energy is eligible by calculation method
without inventing instantaneous power units. RUL and projection are polled,
and the chart displays only actual checkpoint points, elapsed hours, declared
endpoint and dimensionless degradation. Scenario bounds are not confidence
intervals. Energy displays actual methods/coverage/gaps/resets/null losses.
Resource errors remain visible even when last successful data is retained.
The dial formats the backend's long floating-point score to at most two decimal places
for display; it does not recalculate health.
H04 asset selection, abort/race handling, null and freshness rules are preserved.
Fixed-UTC historical scenario events correctly show stale event time despite
successful current API polls. No fixture silently populates monitoring.

## Genuine trace and numerical/API/browser evidence

[Correlated FC04/SQL/API trace](evidence/h06/modbus-sql-trace.json):

```text
asset H06-SIM-05 / unit 1 / map fictional-lv-v1
event 2026-10-09T00:03:25Z / sequence 101
snapshot/hash 2a69dcc0d8545ca7dfbbc596ce764132a720bc26423c385fc0a615a9802a5c05
active power 8.016 kW
receipt COMMITTED
persisted synthetic RUL 79.94305555555547 h
operational fault risk null / prediction confidence null
```

An independent pymodbus client and the bridge decoder agreed on the complete
canonical snapshot. A real broker delivered it, H02 committed PostgreSQL telemetry,
analytics/receipt/checkpoint, and a direct SQL join and bounded read APIs matched
asset/time/sequence/hash/power/RUL. Alert and maintenance lifecycle effects are
covered by real PostgreSQL tests, including no duplicate effects.

[Real API arithmetic results](evidence/h06/api-oracles.json):

| Separate explicit validation scenario | Actual response |
|---|---|
| D=.2, endpoint=1, rate=.01/hour | `SIMULATED_ESTIMATE`, 80 h |
| 10 kW for 2 h | `AVAILABLE`, 20 kWh |
| 0→10 kW in 1 h | `AVAILABLE`, 5 kWh |
| Counter 100→110→2→5 | `PARTIAL`, full consumption null, covered 13 kWh, reset excluded |
| Unverified LIVE-labelled validation input | operational RUL/risk/loss/efficiency and energy null |

The last row is a deliberately unverified integration input, not evidence of a
real device. These HTTP arithmetic scenarios supplement the genuine Modbus
trace; they do not pretend all arithmetic cases came from Modbus.

[Actual browser evidence](evidence/h06/browser.json),
[desktop](evidence/h06/dashboard-desktop.png),
[mobile](evidence/h06/dashboard-mobile.png), and
[80 h oracle](evidence/h06/rul-oracle-browser.png) were captured from the running
React app in actual headless Edge. It fetched real registry/latest/history/RUL/
projection/energy resources, rendered matching accepted timestamps/source labels,
the H05 curve, 80 h, 20 kWh and 5 kWh, and displayed API disconnected/stale state
when actual requests were aborted. Browser failure injection substituted no
response objects. Fixture-driven unit tests are separate evidence and do not
establish live integration by themselves.

## Real outage and recovery evidence

[Outage observations](evidence/h06/outages.json) record stopping only the owned
native test broker and the newly created disposable PostgreSQL cluster, plus
actual bridge/backend process replacement. No operator service was stopped.

After disconnected broker state settled, committed count stayed 252 while pending
durable entries grew from 15 to 21. During SQL outage the broker acknowledgment
count increased while committed count stayed 252. The bridge was stopped with
33 pending entries and reopened the same spool; all pending identities/hashes
survived. Database/broker restart resumed real SQL commits. After actual backend
process replacement, consecutive persisted D values advanced exactly
`.01 × elapsed_event_hours`, within 1e-12, from restored checkpoint state.

Initial outage assertions raced with legitimate receipts for observations already
committed before broker stop; those attempts failed and were corrected to measure
settled disconnected state. A post-outage current-snapshot correlation probe
also timed out while sequential delivery was behind acquisition; the prior
successful complete trace remains valid and is retained. Recovery proves resumed
commits and preservation, not instantaneous full backlog drainage. The two-second
poll configuration provides catch-up opportunities, but pending records remained
during the observed recovery window. No throughput/latency/scale claim is made.

## Commands and actual outcomes

### PASSED

- `git branch --show-current`, `git rev-parse HEAD`, `git status --short` before
  editing; final branch/HEAD unchanged. H06-only delta/hash check.
- Root `docker compose config --quiet` (exit 0).
- Native disposable cluster: PostgreSQL 18 `initdb -U h06_test -A trust --no-locale
  --encoding=UTF8`, `pg_ctl ... -o '-h 127.0.0.1 -p 55433' -w start`, and
  `createdb ... h06_demo`. Originally under a new temporary directory, it was
  stopped and moved to the verified new D: path after C: disk exhaustion.
- From `backend/`, with the disposable DATABASE_URL:
  `python -m alembic upgrade head` (exit 0), fresh upgrades 0001→0002→0003→0004.
- Installed approved ML wheel:
  `python -m pip install --no-deps --force-reinstall "$env:TEMP/h05-final-runtime-wheel/transformer_ml_runtime-0.1.0-py3-none-any.whl"`.
  Simulator installation: `python -m pip install --no-deps --no-build-isolation
  "$env:TEMP/h06-simulator-install-source"` (exit 0), after narrow export.
- Isolated pytest/pymodbus/paho and AMQTT dependency installs as documented in
  the runbook (exit 0). Broker installation printed an unrelated globally
  installed fastapi-cli/typer conflict warning; isolated target was used.
- Native commands: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
  --workers 1`; `python simulator/scripts/native_broker.py`;
  `python -m simulator.cli modbus-server --config simulator/config/hackathon-native-server.json`;
  `python -m simulator.cli modbus-bridge --config simulator/config/hackathon-native-bridge.json`.
  Actual API health/resource requests succeeded.
- `python simulator/scripts/demo_runtime.py setup --native`, `check --native`,
  `replay --native`; `python simulator/scripts/demo_oracles.py`; independent
  `demo_probe_modbus.py`; initial `demo_trace.py` (exit 0).
- `--help` for the actual modbus-server/modbus-bridge/replay-canonical CLI,
  driver and probe; Git Bash wrapper syntax and setup help; prepared `25 --help`.
- With isolated test dependencies and
  `TEST_DATABASE_URL=postgresql+psycopg://h06_test@127.0.0.1:55433/postgres`, from backend:

  ```powershell
  python -m pytest tests/read_api/test_latest.py tests/read_api/test_history.py tests/alerts/test_lifecycle.py tests/alerts/test_concurrency.py tests/test_h06_resources.py tests/test_h02_postgres.py tests/test_migrations.py tests/hardening/test_repository_recovery.py -q --tb=short
  ```

  **61 passed**, exit 0, 37.23 s, one Starlette/httpx deprecation warning. Fixtures
  create/drop unique disposable PostgreSQL databases. This covers real commit
  receipt visibility, exact retry/conflict/late records, rollback after candidate
  inference, restart/incompatible checkpoints, registry/provenance, migrations,
  read projections and alert/maintenance lifecycle. Earlier smaller run: 13 passed.
- From simulator, `python -m pytest tests/test_runtime_h06.py tests/test_modbus_h03.py
  tests/test_delivery_h03.py -q`: **18 passed**, exit 0, 31.97 s. Includes real
  loopback server/client, bounded spool/retry, pre-roll and container-bind opt-in.
- From frontend: `npm.cmd ci --ignore-scripts` (193 installed, zero reported
  vulnerabilities), `npm.cmd run build`, `npm.cmd run lint` (exit 0; 16 existing
  warnings), and `npm.cmd test -- tests/h06-resources.test.tsx tests/resources.test.tsx
  tests/client.test.ts tests/polling.test.tsx`: **29 passed**, four files, exit 0.
- Actual Edge smoke: `node simulator/scripts/demo_smoke_browser.mjs`; temporary
  `npm.cmd install --prefix "$env:TEMP/h06-browser" --no-save --ignore-scripts
  playwright-core` provided the smoke driver only, not a frontend fallback.

### FAILED attempts / diagnosed

- Initial Docker daemon queries failed because its Linux engine pipe was absent.
  After starting Desktop, `docker compose up --build -d` built the backend wheels
  and frontend but failed exporting simulator layers:
  `mkdir /var/lib/desktop-containerd/daemon/tmpmounts/containerd-mount2013001560:
  input/output error` (exit 1). C: became exhausted. Subsequent image/Compose
  commands reported blob I/O errors; Desktop restart did not yield a usable
  engine. No unrelated images/volumes/data were deleted.
- Initial migration from the wrong working directory failed with missing
  `script_location`; corrected backend invocation passed.
- Initial focused PostgreSQL runs exposed projection/protection bugs and stale
  test-contract assumptions described above. Intermediate results included
  6 failed/23 passed/18 errors, then 6 failed/42 passed and 5 failed/55 passed;
  final corrected run is 61 passed. Assertions were not removed to force green.
- Initial frontend commands from root failed ENOENT; corrected cwd passed.
  A temporary Windows text encoding mistake caused build/lint failures and was
  repaired to UTF-8. Final `npm ci` initially failed EPERM because the owned Vite
  process held a native module; stopping that process allowed a clean rerun.
- Initial outage race assertions and post-outage current probe timeout are
  recorded above. They are not counted as passed acceptance.

### SKIPPED / not rerun

The first 13 SQL tests skipped without TEST_DATABASE_URL; the subsequent real
PostgreSQL runs replaced those skips with actual evidence. Completed H00 fixture,
H01 release/regression/packaging, H05 algorithm suites and entire earlier phase
suites were not rerun. Conditional physical RUL/measured savings, public/live
equipment control, horizontal state consistency and H07 load/soak were not
attempted. `demo_25` is a prepared H07 handoff, not a completed scale test.

### BLOCKED / remaining acceptance

The original Docker engine/storage blocker was resolved; clean builds, fresh
Compose startup, PostgreSQL 16/Mosquitto and container-to-browser evidence are
now available. Authentic fitted artifacts and verified physical lifetime/loss
inputs remain unavailable; the explicit demo-unverified mode is the supported
fictional demonstration. Full thermal/history readiness is not established by the sparse
pre-roll or unverified demo thermal units; component coverage remains honestly
reduced/unavailable. Real bad-quality/bridge-stop visual failure rehearsal beyond
the protocol unit checks and actual API-outage browser check was not completed.
The earlier recovery attempt retained/resumed its backlog but did not prove
complete tracked delivery; see the continuation evidence below. A PostgreSQL restart drops the existing advisory
runtime lease; the runbook requires restarting the single backend to reacquire
it. Automatic lease recovery/horizontal ownership is not claimed. Fitted artifacts/lifetime/loss
evidence remain missing; risk, operational RUL, losses/efficiency stay null.

The exact next dependent phase is **H07 — portfolio scale/soak and final demo
rehearsal**, after manual H06 acceptance and agreement on the disclosed remaining
limits. H07 was not begun. No earlier phase was rebuilt or its entire suite rerun.

## Container resolution and evidence recovered during continuation

The existing disposable project is `transformer-h06-20261009`; existing operator
and earlier project volumes were preserved. The subsequent successful commands
were `docker compose config`, `docker compose up --build -d`, `docker compose ps`,
`python simulator/scripts/demo_runtime.py setup`, and the primary Modbus/bridge
commands. All six services started; database/backend/frontend/broker/Modbus health
checks passed. Image packaging installs ML at
`/usr/local/lib/python3.12/site-packages/ml/__init__.py` (Python 3.12.15, runtime
package 0.1.0), with the explicit `DEMO_UNVERIFIED_CONFIG` identity already declared
above. Fresh entrypoint migrations reached `0004` from `0001` on PostgreSQL 16.
The simulator reuses the backend ML image build context; `.dockerignore` excludes
owned native spools so locked SQLite journals do not enter image export.

[Container FC04 → bridge → Mosquitto → PostgreSQL → API trace](evidence/h06/container/modbus-sql-trace.json)
correlates `H06-SIM-05`, event `2026-10-09T00:01:20Z`, sequence 76,
`snapshot/hash=059727860a9964587ab6134dc720db95b193f937b7d80eb8ed8cf70550f410fd`,
36.054 kW, receipt `COMMITTED`, and persisted synthetic RUL
79.97777777777772 h. Risk/confidence remain null. This is genuine container
acceptance, separate from the earlier native trace retained above.

[Container arithmetic API responses](evidence/h06/container/api-oracles.json)
confirm 80 h, 20 kWh, 5 kWh, excluded counter reset and null unverified operational
outputs. [Actual compiled React/Edge evidence](evidence/h06/container/browser.json),
[desktop](evidence/h06/container/dashboard-desktop.png),
[mobile](evidence/h06/container/dashboard-mobile.png) and
[RUL oracle](evidence/h06/container/rul-oracle-browser.png) show the real API
responses and projected curve through Nginx on 5173. API request abortion produced
visible disconnected/error state; this is not a claim that every service-stop UI
fault rehearsal was executed. UI fixture tests are separate evidence.

**PASSED:** with `TEST_DATABASE_URL` pointed only at the disposable local
PostgreSQL 16 instance and isolated test dependencies, from `backend/`:

```powershell
python -m pytest tests/test_migrations.py tests/test_h02_postgres.py tests/test_h06_resources.py tests/hardening/test_repository_recovery.py -q
```

13 passed, one deprecation warning, exit 0, 23.02 s. This focused container run
used unique disposable test databases. It was completed before this continuation
and was not rerun merely to reconfirm it.

[Previous container failure-run evidence](evidence/h06/container/failures.json)
records successful real exact retry, HTTP/MQTT conflict, injected analytics SQL
rollback, broker/database outages, five retained identities across bridge restart
and resumed commits with correct restored degradation. Its `completed=true`
only establishes resumed delivery: `fully_drained=false` explicitly records the
remaining backlog at that observation, rather than claiming complete recovery.

**FAILED intermediate attempts preserved:** the initial MQTT diagnostics request
used `/api/v1/mqtt/status` and returned 404; the actual route is
`/api/v1/ingest/mqtt/status`. The eight-second broker-reconnect PUBACK wait then
timed out while the bridge retained its configured retry backoff (maximum 30 s).
Services were restored without deleting a spool or volume. The subsequent
45-iteration attempt resumed commits but did not verify each retained receipt.
The first container setup JSON parsing attempt also failed because build output
preceded its JSON; parsing the actual final JSON line and `-T` fixed that boundary.
These intermediate failures do not invalidate, or replace, later actual evidence.

## Narrow recovery continuation — prior failed attempts (2026-10-10 local)

The existing runner is `simulator/scripts/demo_container_failures.py`. Added
`--recovery-only` to avoid rerunning already-proven conflict/rollback gates.
Its PUBACK deadline derives from the actual bridge configuration:
30 s maximum backoff + 2 × 2 s timeout + 2 × 2 s polling + 10 s margin = 48 s.
The recovery deadline additionally allows bounded sequential delivery of the
captured entries (maximum 300 s). Assertions retain committed-count invariance
during outages, rising real PUBACK while SQL is unavailable, durable hashes
across bridge restart, matching committed receipts for **all** captured identities,
one SQL telemetry/analytics pair each, and correct checkpoint degradation rate.
A short owned bridge pause permits a stable exact-retry comparison including
telemetry, analytics, alerts, maintenance and checkpoint bytes.

Actual continuation command (project guard refuses any other project):

```powershell
$env:COMPOSE_PROJECT_NAME='transformer-h06-20261009'
$env:PYTHONPATH="$env:TEMP/h06-test-dependencies"
python simulator/scripts/demo_container_failures.py --recovery-only
```

**FAILED:** the command above was run twice, both exit 1. First, every captured
identity had a committed receipt, but the immediate spool-removal assertion ran
before the bridge's next delivery poll. Evidence is retained as
[continuation attempt 1](evidence/h06/container/recovery-continuation-attempt1.json).
The test was corrected to wait, within the same bounded deadline, for both matching
receipts and removal/counter advancement. No assertion was removed.

The second/latest run stopped earlier at the broker-outage invariant:

```text
File "simulator/scripts/demo_container_failures.py", line 99
assert after['counters'].get('committed',0)==before['counters'].get('committed',0)
AssertionError
```

[Latest failed-run evidence](evidence/h06/container/recovery-continuation.json)
has `completed=false`. The fixed five-second broker-stop settling period does not
establish that confirmation of previously committed observations has finished;
this is consistent with the earlier observed receipt-settling race. This failure
must be diagnosed using the pending identities' SQL/receipt state, and the test
must establish an appropriate settled measurement boundary before retry. It does
not justify disabling the invariant or treating PUBACK as commit. Diagnostics
are now saved before that invariant so any future attempt retains both counter
snapshots; **that final diagnostic-only edit has not been rerun**. Per the narrow
continuation stop condition, no further outage attempt or broad suite was run.
The stable recovered-retry side-effect comparison and final rate assertion in
this new recovery-only run were not reached; earlier real retry/rollback/rate
proof remains in `failures.json` and was not relabelled as new evidence.

**PASSED read-only follow-up (exit 0):**
[actual retained-identity receipts/SQL/API state](evidence/h06/container/recovery-follow-up.json)
confirms all five identities captured during attempt 1 now have matching
`COMMITTED` receipts and exactly one PostgreSQL telemetry row and one associated
analytics row each. Example: `9aacd20d90f6ab37bdc2a8c9ec0bf30c7305b62d1917d9cfbfb80bfec3ce9514` → `COMMITTED`, telemetry ID 607, one analytics row; all five exact hashes are listed in the evidence. No broad replay or new
SQL injection was performed for this follow-up. Direct HTTP checks returned 200
for `/health/ready`, `/api/v1/transformers/H06-SIM-05/rul`,
`/api/v1/transformers/H06-SIM-05/energy?window=1h&anchor=latest` and the actual
frontend at 5173. This proves resumed delivery of those records, not a passing
outage acceptance test or complete steady-state backlog drainage.

**Final service state:** the runner restored only the owned disposable services.
`docker compose ps` showed all six up, with database, broker, backend, frontend
and Modbus simulator healthy; bridge running and connected. Recent actual bridge
logs showed committed count advancing from 456 to 461 and pending spool usage
around 19–21 records. The backlog was retained, not cleared. Existing volumes,
images, database data and prior spool records were preserved.

**Other continuation checks:** runner `--help` exit 0, Python AST syntax exit 0,
report local-link validation exit 0. Final branch remains `develop`, HEAD remains
`29dcfaf5e12ef50446d1106c4994a721dc802476`. No prior broad test/build/setup was
repeated. Only this existing failure runner, this report and continuation evidence
were changed during the resumed work.

**Remaining acceptance:** settle/diagnose and rerun the strict recovery-only gate;
complete the still-unrun visual bridge-stop/bad-quality rehearsal and agree on
adequate thermal/history pre-roll coverage. Authentic fitted release and physical
operational inputs remain unavailable as already declared. No infrastructure
blocker is currently claimed for the running Compose path. H06 is available for
manual review of partial evidence, **not final phase acceptance**. H07 remains
unstarted and dependent on H06 acceptance.


## Strict broker-outage diagnosis and deterministic gate (second continuation)

[Retained broker/bridge logs and PostgreSQL receipt times](evidence/h06/container/strict-diagnosis-history.json)
establish the previous outage at **19:06:39–19:06:56 UTC**. Bridge diagnostics
show delivery `committed` 448 at 19:06:44 and 449 at 19:06:50, while PUBACK
stayed 555. SQL has **no new H06-SIM-05 receipt commits during that outage**;
the latest preceding receipt committed at 19:06:38.289930 UTC. The global spool
counter counts delivery confirmations, not SQL transactions occurring at that
instant. The worker checks an existing SQL receipt before attempting MQTT, so
an earlier SQL commit can be confirmed after broker disconnection. The missing
original before/after identity set prevents naming the exact removed snapshot
retrospectively; that limitation is preserved rather than guessing its identity.

The actual installed `DeliveryWorker` reproduced the mechanism with a known
already-committed identity: while MQTT was observably unreachable, a matching
real SQL receipt allowed its isolated spool counter to advance from 0 to 1,
with zero PUBACKs and no new SQL insertion. This is legitimate delayed receipt
confirmation, not a queued record gaining commit status without a receipt.
The old global invariant mixed that outstanding confirmation with newly queued
source data. No production bridge/receipt correctness defect was found or
patched; only the acceptance synchronization/identity scoping changed.

The existing `demo_container_failures.py --recovery-only` now controls a unique
fictional asset and a separate bounded spool (20 records, 128 KiB payload) within
the existing spool volume. The ongoing source and its original spool are retained.
A stopped helper is retained for diagnostics; no containers, volumes, images,
records or spools are deleted. The helper uses the **actual installed bridge
image and code**, real Compose network, Mosquitto and backend/PostgreSQL.
The full-run branch delegates to the same corrected gate, but its already-proven
conflict/SQL rollback portion was not rerun in this continuation.

Observable sequence: Docker reports broker stopped; an actual TCP attempt from
the bridge helper reports unavailable; old receipt confirmation is accounted for;
only then is a unique post-outage snapshot created and enqueued. The actual worker
reports `BROKER_FAILURE` and disconnected publisher. During at least 10 seconds
(three 2-second polling intervals plus two 2-second timeouts), its snapshot stays
pending, receipt stays HTTP 404, SQL rows stay absent, PUBACK stays zero, and its
isolated committed count remains at the established baseline. Attempts and
`next_attempt` are persisted and honored; retry/backoff is not disabled.

After helper restart preserves the pending entry/hash/counters, the real broker
is restored. A 48-second monotonic deadline covers the configured maximum
30-second backoff plus timeout/poll margins. Passing requires matching H00 receipt,
spool removal, exactly one telemetry/analytics pair and one checkpoint observation.
HTTP retry compares all asset telemetry/analytics/alerts/maintenance/checkpoint
state. For MQTT reconnect retry, the owned primary bridge is briefly paused and
backend queue/counters must settle observably before measuring its duplicate
counter; the primary bridge is then unpaused in `finally`.

**PASSED initial corrected gate:**
[run 51230402](evidence/h06/container/strict-recovery-51230402.json), exit 0:
new snapshot `21e76b2f23c09effee8631814d60ce92fabe3ce5a6fbeb3e4ed9bcd2b0459da6`,
telemetry ID 883, one analytics row and one checkpoint observation. Baseline 1
stayed unchanged offline; recovery reached 2 only with a matching committed
receipt. The final run below adds explicit MQTT counter isolation.

**FAILED intermediate launch:**
[run 802ce1b7](evidence/h06/container/strict-recovery-802ce1b7.json), exit 1,
`unknown flag: --no-build` from the installed Compose `run` command, before any
outage started. The initial successful helper launch had triggered a cached backend
build through Compose's build dependency. The final launcher therefore uses
`docker run` with the inspected existing immutable bridge image ID, network and
`--volumes-from`; it cannot build an image. This precise correction avoids new
packaging/setup work. A reporting helper also initially used the simulator cwd
and raised FileNotFoundError; rerunning that read/edit helper from root corrected
it without production changes.

**PASSED directly related units:** from `simulator/`, with isolated existing test
dependencies:

```powershell
python -m pytest tests/test_delivery_h03.py::test_spool_restart_puback_not_commit_and_real_receipt_shape tests/test_delivery_h03.py::test_no_false_commit tests/test_delivery_h03.py::test_http_connection_failure_and_broker_failure -q
```

5 passed, exit 0, 6.58 s. These supplement real-service evidence, not replace it.

**PASSED final strict gate:**
[run 4121588e](evidence/h06/container/strict-recovery-4121588e.json), exit 0, using
existing immutable images with no build. Actual command from root:

```powershell
$env:COMPOSE_PROJECT_NAME='transformer-h06-20261009'
$env:PYTHONPATH="$env:TEMP/h06-test-dependencies"
python simulator/scripts/demo_container_failures.py --recovery-only
```

Asset `H06-STRICT-4121588e`; new snapshot and expected semantic hash:
`e02cccdc16abcc38b4a7424aa67950054037bdcc7ce118a1846deb76f15efd0b`.
Offline baseline committed count **1** accounts only for the preceding known SQL
receipt; the new identity stayed pending with **HTTP 404/no SQL rows/zero PUBACKs**
and unchanged count. After recovery its receipt was `COMMITTED` with that exact
hash, telemetry ID **977**, exactly **one telemetry row/one analytics row**, and
checkpoint observation count **1**. Delivery counter reached **2**, attributable
to the old receipt and the new accepted identity; two recovery PUBACKs did not
produce two accepted rows. Restart retained the pending entry/hash/attempts.
A real MQTT reconnection republishes the accepted identity after the owned
producer/consumer setup barrier; both that retry and HTTP retry left telemetry,
analytics, alerts, maintenance and checkpoint unchanged. The counter remained 2.

| Diagnosis possibility | Evidence and conclusion |
|---|---|
| Legitimate pre-outage publication/receipt | Historical counter advanced without any new SQL receipt commit; a known pre-committed identity reproduces receipt-first confirmation offline. SQL committed before the outage, rather than a new post-outage transaction. |
| Queued record falsely counted committed | Not observed: new identity has 404/no rows and unchanged count throughout offline observation; only matching actual SQL receipt allows removal/count advancement. |
| Unrelated work included in global counter | Original counter covers the ongoing stream and its outstanding confirmations. New gate controls one post-outage asset/identity and isolated spool counter; unrelated confirmations cannot satisfy it. |
| Genuine bridge/receipt defect | None found in this targeted investigation. Installed production logic and receipt verification were used unchanged. Original removed identity is not retrospectively recoverable from the failed run's missing snapshots. |

**PASSED final bounded smoke:**
[HTTP/receipt/timestamp evidence](evidence/h06/container/strict-final-smoke.json),
exit 0: ready/latest/RUL/energy/frontend HTTP 200, main asset `H06-SIM-05` latest
snapshot has matching committed receipt and telemetry/analytics timestamps.
`docker compose ps` shows six services up, with all five configured health checks
healthy and the primary bridge unpaused/running. The stopped test helpers and
their bounded spools remain available; no existing source data/spool was removed.

**PASSED:** final runner Python AST check, report local links and unchanged
branch/HEAD check. **FAILED:** historical strict attempts and unsupported-launch
attempt remain recorded above. **SKIPPED:** default full conflict/rollback branch,
previous complete phase suites, broad browser/Modbus/RUL/energy/PostgreSQL suites
and H07 load/soak were not repeated. **BLOCKED:** no database/broker infrastructure
blocker remains for this specific gate. Fitted artifacts and verified physical
lifetime/loss evidence remain unavailable; demo results do not imply fitted or
operational readiness.

**Current remaining limitations:** strict broker-outage recovery is **PASSED**.
The sparse pre-roll still does not establish full thermal/feature coverage;
real bridge-stop/bad-quality visual rehearsal remains unrun. Complete drainage
of the continuously generating main spool/throughput is not claimed by this
isolated test. The prior actual database-outage evidence and five-identity recovery
remain valid and were not rerun. H06 evidence is ready for manual review with
these limits, not an automatic declaration of full phase acceptance. H07 remains
unstarted. This continuation changed only the existing runner/report and five
new evidence JSON files listed in the path inventory.


## Exact H06 path inventory

Paths below are the exact H06 delta against the pre-H06 hash inventory; prior
H00–H05 changes outside this list were preserved. A path already modified by a
prior phase appears here only when H06 additionally changed it.

- `.dockerignore`
- `.env.h06.example`
- `backend/Dockerfile`
- `backend/app/api/v1/analytics_resources.py`
- `backend/app/api/v1/router.py`
- `backend/app/core/config.py`
- `backend/app/schemas/telemetry.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/analytics_resources.py`
- `backend/app/services/hooks.py`
- `backend/app/services/ingestion_service.py`
- `backend/app/services/transactional_ml.py`
- `backend/tests/alerts/test_lifecycle.py`
- `backend/tests/hardening/test_repository_recovery.py`
- `backend/tests/read_api/conftest.py`
- `backend/tests/read_api/test_history.py`
- `backend/tests/test_h06_resources.py`
- `docker-compose.yml`
- `docs/hackathon_readiness/execution/H06_RUNTIME_AND_SINGLE_ASSET_INTEGRATION.md`
- `docs/hackathon_readiness/execution/evidence/h06/api-oracles.json`
- `docs/hackathon_readiness/execution/evidence/h06/browser.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/api-oracles.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/browser.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/dashboard-desktop.png`
- `docs/hackathon_readiness/execution/evidence/h06/container/dashboard-mobile.png`
- `docs/hackathon_readiness/execution/evidence/h06/container/failures.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/modbus-sql-trace.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/recovery-continuation-attempt1.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/recovery-continuation.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/recovery-follow-up.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/rul-oracle-browser.png`
- `docs/hackathon_readiness/execution/evidence/h06/dashboard-desktop.png`
- `docs/hackathon_readiness/execution/evidence/h06/dashboard-mobile.png`
- `docs/hackathon_readiness/execution/evidence/h06/modbus-sql-trace.json`
- `docs/hackathon_readiness/execution/evidence/h06/outages.json`
- `docs/hackathon_readiness/execution/evidence/h06/primary-api.json`
- `docs/hackathon_readiness/execution/evidence/h06/rul-oracle-browser.png`
- `frontend/Dockerfile`
- `frontend/src/api/client.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/components/HealthIndexDial.tsx`
- `frontend/src/components/InteractiveTwinStudio.tsx`
- `frontend/src/components/ResourceCards.tsx`
- `frontend/tests/h06-resources.test.tsx`
- `frontend/tests/h06-serialized.json`
- `simulator/.gitignore`
- `simulator/Dockerfile`
- `simulator/H03_RUNBOOK.md`
- `simulator/H06_RUNBOOK.md`
- `simulator/config/analytics-policy.json`
- `simulator/config/artifacts/README.md`
- `simulator/config/hackathon-25.yaml`
- `simulator/config/hackathon-bridge.yaml`
- `simulator/config/hackathon-native-bridge.json`
- `simulator/config/hackathon-native-server.json`
- `simulator/config/hackathon-single.yaml`
- `simulator/config/replay-canonical.jsonl`
- `simulator/scripts/demo_25.sh`
- `simulator/scripts/demo_check.sh`
- `simulator/scripts/demo_container_failures.py`
- `simulator/scripts/demo_oracles.py`
- `simulator/scripts/demo_primary.sh`
- `simulator/scripts/demo_probe_modbus.py`
- `simulator/scripts/demo_replay.sh`
- `simulator/scripts/demo_runtime.py`
- `simulator/scripts/demo_setup.sh`
- `simulator/scripts/demo_smoke_browser.mjs`
- `simulator/scripts/demo_trace.py`
- `simulator/scripts/native_broker.py`
- `simulator/simulator/modbus_server.py`
- `simulator/tests/test_runtime_h06.py`
- `docs/hackathon_readiness/execution/evidence/h06/container/strict-diagnosis-history.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/strict-recovery-51230402.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/strict-recovery-802ce1b7.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/strict-recovery-4121588e.json`
- `docs/hackathon_readiness/execution/evidence/h06/container/strict-final-smoke.json`
