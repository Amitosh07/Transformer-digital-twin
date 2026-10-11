# H07 portfolio and judging rehearsal

Executed 2026-10-10 IST (captured UTC times are 2026-10-09). Branch develop,
HEAD `29dcfaf5e12ef50446d1106c4994a721dc802476`, with the existing reviewed
uncommitted H00â€“H06 work. No commits, pushes, destructive cleanup, public
deployment or real equipment access. Earlier suites and implementations were
not rebuilt. **The 25-asset capacity target failed; final portfolio acceptance
is not claimed.** Single-asset resource/browser checks remain usable, but a
fresh current-snapshot receipt rehearsal timed out with retained backlog.

## Files and ownership

Changed existing integration helper `simulator/scripts/demo_runtime.py` to
execute the H07 measurement driver, accept duration/evidence-directory options,
and prevent primary Compose from rebuilding/recreating existing services.
Appended only the 25 new fictional policies to
`simulator/config/analytics-policy.json`; existing entries were preserved.
Created `simulator/scripts/demo_portfolio.py`, `demo_portfolio_browser.mjs`,
`demo_judging_browser.mjs` and `demo_portfolio_evidence.py`.
Created run configuration `simulator/config/h07-dfb1b1/server.json` and
`bridge.json`. Created this report, [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md),
[ACCEPTANCE_RESULTS.md](ACCEPTANCE_RESULTS.md), and the evidence files indexed
by [the run manifest](evidence/h07/soak-dfb1b1/manifest.json),
[summary](evidence/h07/soak-dfb1b1/summary.json),
[assertions](evidence/h07/soak-dfb1b1/evidence-assertions.json),
[baseline](evidence/h07/baseline/primary-api.json) and
[primary resources](evidence/h07/primary/primary-api.json).
The final scope audit provides the exact file inventory under
`evidence/h07/final-verification.json`. No production backend, frontend, ML,
simulator algorithm, Modbus map, frozen contract or prior phase report was edited.

## Environment and baseline

Actual Intel i7-13620H, 10 cores/16 logical processors, 16,857,817,088 bytes RAM,
Windows 11 build 26200; Docker 29.7.2 Linux engine, observed container memory
limit 7.606 GiB. Host Python 3.13.7, Node 22.17.0; installed container Python
3.12, ML package 0.1.0, pymodbus 3.6.9, paho 2.1.0, PostgreSQL 16 and actual
Mosquitto 2.1.2. Evidence: [hardware](evidence/h07/soak-dfb1b1/hardware.json)
and retained container logs. Existing project `transformer-h06-20261009` uses
loopback ports 55433/51885/8001/5173/1502. Additional H07 source used loopback
1503 and existing internal Docker network. Its immutable image was
`sha256:8bc50892ab800f8018556e61b8f14c080511ffe98f548bd244e4f0fa1ff5f3ca`.
No new image builds were needed. The actual primary ML runtime remains explicit
DEMO_UNVERIFIED_CONFIG, bundle `demo_unverified_coded_config_v1`.
Authentic fitted artifacts, validated forecast risk/confidence, operational
lifetime and unverified physical loss/efficiency remain unavailable.

Initial `demo_check.sh` succeeded against actual readiness, latest, RUL, energy
and registry resources. Services were healthy. The existing historical H06
event clock is intentionally stale and is not a live-clock latency measurement.

## Genuine load attempt and measurements

Executed `bash simulator/scripts/demo_25.sh --duration-seconds 1800` using
`C:/Program Files/Git/bin/bash.exe`. This invoked the existing H03 scheduler,
read-only FC04 server/bridge, actual broker, SQL ingestion, ML and React.
25 unique fictional H07-dfb1b1-01 through -25 assets used units 1â€“25, seeds
42â€“66, five-second source cadence, fictional 30 kVA/400 V LV configuration,
map `fictional-lv-v1`, gateway H07-dfb1b1. Policies use declared synthetic
RUL versions/rates and H05 power integration, never browser calculations.

Source start: `2026-10-09T19:36:30.017775Z`. Measurement began
`19:36:35.718308Z` and ended `19:51:27.280917Z`: **891.5626 seconds**, not
1800 seconds. Exit 1: host C: free space fell below the 512 MiB safety boundary.
All 25 had accepted rows, but neither full-duration activity nor cadence delivery
was achieved. The cause of transient host disk consumption was not conclusively
attributed; no data/volume/image deletion was used. Free space later recovered
without destructive cleanup. A sustainable portfolio count has not been measured;
one functional H06 asset is not evidence of a smaller 30-minute capacity target.

| Measurement | Actual result and scope |
|---|---|
| Expected event observations within measured bounds | 178 per asset; 4,450 total |
| Committed within measurement cut-off | 756 (17.0%); per-asset counts/fractions in summary |
| Accepted after run / analytics | 819 / 819; distinct accepted sequences, no trip contamination |
| Durable spool inspection after stop | acquired 2,050, broker PUBACKs 2,088, receipt-confirmed committed 803, pending 1,247 |
| Observed spool peak | 1,252 records in retained bridge logs; sampled peak was 1,150 |
| Sampled backend queue peak | 99; missing samples make this a lower bound |
| Successful API measurement latency | n=44; p50 62.1 ms, p95 369.4 ms, max 478.7 ms |
| API measurement failures | 16 timeouts, excluded from latency percentiles explicitly |
| Live-event-clock to matching visible snapshot | n=167; p50 178.706 s, p95 381.826 s, max 683.246 s |
| Backend received timestamp to visible snapshot | n=167; p50 10.172 s, p95 46.899 s, max 332.430 s |
| Persisted receipt timestamp to visible snapshot | n=167; p50 10.172 s, p95 46.898 s, max 332.430 s |
| Browser error observations | 31; observer exit 1 on termination/failure at shortened run, not full-soak PASS |
| Minimum sampled C: free bytes | 492,781,568; later spot checks lower; safety stop preserved data |

The exact acquisition-wall-time per identity is not exposed, so the proposed
acquisition-to-visible metric cannot be claimed measured precisely. Live-event
age uses current simulation UTC, never old replay time. Receipt `committed_at`
is the persisted timestamp and equals received_at in these rows; it is not an
independent PostgreSQL commit-wall-clock instrument. Raw browser field named
`receipt_to_visible_ms` actually used received_at; summary corrects that label,
and the collector has been renamed for subsequent runs. The p95 target below
10 seconds was not established and observed result ages clearly exceed it.
Some measurement errors printed active_sql_assets=0 because SQL collection was
skipped; this is missing evidence, not all assets disappearing.

Per-asset generated counts are cadence expectations, not measured scheduler
production counters. Per-asset rejected/dropped/received counters are unavailable
apart from accepted SQL and missed-snapshot diagnostics. No invented totals.
Memory samples are retained verbatim in assertions/measurements; representative
source 149.1 MiB, bridge 121.5 MiB, backend 391.7 MiB, PostgreSQL 93.47 MiB;
later direct backend sample 498.2 MiB. Missing sampling prevents a true peak claim.
No restarts were intentionally introduced during the measured interval.

## Isolation and recovery evidence

Only asset 01 had OVERLOAD at event offsets 120â€“150 seconds and ALARM_TRIP
150â€“180 seconds. [Final SQL/checkpoints](evidence/h07/soak-dfb1b1/final-isolation.json)
and [actual API/energy snapshots](evidence/h07/soak-dfb1b1/isolation-0246.json)
compare it with 02/03. Asset 01 has four trip rows, urgent maintenance and a
latched trip; all other 24 have zero trip rows. Neighbors have independent
timestamps, histories, thermal states, hash identities, anomaly persistence,
maintenance and degradation. The evidence assertion command verifies 99
distinct hashes/paired analytics across the three compared assets and separate
degradation transformer IDs. Actual final D values were 0.200638889,
0.201645278, 0.202651667; own rates 0.01/0.0101/0.0102 per hour. Thermal
states 39.47249/39.46936/39.46360 are unverified source-unit model states;
they do not establish operational temperature accuracy. Fault asset HI=0,
neighbors approximately 69.88/70.07 with WATCH reasons, not blanket healthy.
Only the fault asset carries trip/overload/urgent effects. Neighbor baseline
warnings remain their own. Energy responses retain own identities, source,
gaps/coverage and null physical loss fields. No counter-reset fault was injected
in this load; H05/H06 reset evidence is reused rather than claimed newly tested.

The affected source was isolated by stopping only owned H07 containers. Its
unresolved latch was deliberately preserved. Restart/rollback/idempotence and
strict broker/SQL outage proofs are reused from H06 with their original scope;
they were not rerun or rewritten. [Source interruption](evidence/h07/soak-dfb1b1/source-interruption.json)
uses bounded pause of the primary source/bridge, a real FC04 timeout and restored
read. Individual unit restart and corrupted-quality browser tests remain NOT RUN.

[Browser switching](evidence/h07/soak-dfb1b1/judging-switch.json) delayed an
actual asset-A response and verified asset-B identity/hash remained selected.
[Browser outage](evidence/h07/soak-dfb1b1/judging-outage.json) stopped the actual
backend, observed API disconnected/retained stale data and unchanged last-success,
and restored it. This covers H06's deferred visible API-failure rehearsal.

## Primary and fallback commands; failures preserved

PASS exit 0: initial and final `demo_check.sh --evidence-directory .../baseline`
or `.../primary`, actual RUL/energy/registry/readiness requests; switching and
outage Node drivers; `demo_replay.sh --native` (two accepted historical events);
corrected replay browser driver; evidence assertions. All browser data came from
actual HTTP responses, no hidden fixture fallback.

Primary helper initially recreated backend through Compose despite no requested
rebuild. The narrowly corrected command uses supported
`up --no-build --no-recreate -d modbus-bridge`; its rerun exited 0 and backend
container identity remained unchanged. This does not erase the intermediate
recreation. Replay browser attempt 1 raced registry loading; attempts 2/3 used
the wrong live-stale wording/Windows text encoding. A registry-ready barrier and
the actual Historical replay label corrected the test, not the application.
All failed attempt JSONs remain in the run directory. Final replay DOM shows
REPLAYED, H06-RUL-ORACLE/H06-R1 origin/run, source event `2026-10-09T00:00:05Z`
and separate successful poll time. Primary continued separately. HTTP fallback
is not substitute Modbus proof.

FAILED: optional new `demo_trace.py --database-url <disposable local DSN>
--evidence-directory .../primary` timed out waiting for the current snapshot's
receipt after five attempts. An initial attempt while the source was paused
failed at FC04; the subsequent unpaused attempt failed the receipt assertion.
The bridge later reported 152 pending records and connected source, consistent
with backlog. No claim of a new correlated current trace is made; H06's earlier
independent FC04/SQL/API/DOM trace remains valid historical evidence. The helper
still lacks clean ModbusIOException handling on stopped-server probes; the
separate H03 SnapshotPoller correctly reports the interruption.

SKIPPED: prior completed suites, packaging/builds and full H06 recovery suites;
no regression justified repeating them. BLOCKED/NOT RUN: full 30-minute capacity,
exact acquisition/commit instrumentation, sustainable smaller-count rehearsal,
complete one-hour thermal coverage, fitted artifact release, fresh human teammate
execution and independent per-unit restart. No operational accuracy, transformer
lifetime, measured efficiency/savings or compliance claim is made.

## Final state and handoff

H06 PostgreSQL, broker, backend, frontend, primary source and bridge remain running
on loopback, with database/migrations and demo ML readiness. H07 source/bridge and
read-only inspection helper remain retained/stopped; pending spool, database
rows, configurations and screenshots remain available. Do not clear backlog or
restart the same deterministic source casually. No volume/image/row deletion.

Use [runbook](DEMO_RUNBOOK.md) and [acceptance matrix](ACCEPTANCE_RESULTS.md) for
manual team review. The single-asset resources and replay can be presented with
explicit freshness/readiness limitations. The measured portfolio is **not ready
to claim the 25-asset/30-minute/10-second target**. Before judging, allocate adequate
disk headroom, diagnose delivery throughput with retained measurements, obtain a
fresh correlated primary receipt and perform an independent teammate rehearsal.
No next implementation phase was started; the next handoff is final manual
acceptance and capacity/remediation decisions.

Final verification: python simulator/scripts/demo_portfolio_evidence.py .../soak-dfb1b1 exit 0; 99 isolated SQL/hash pairs, 756 within-cutoff commits and 819 post-run pairs. The first assertion-driver attempt used an incorrect checkpoint wrapper path and failed KeyError; inspection corrected it to the established state_version/payload shape, with no checkpoint changes. python -m json.tool ran on 24 new JSON files, exit 0; JSONL parse, Python AST, both Node --check commands and demo_runtime.py --help passed. Local Markdown links resolved. SHA-256 comparison against the pre-H07 dirty-file inventory found only the two declared existing integration/config paths changed; no earlier implementation/report hashes changed. Final bounded demo_check.sh --evidence-directory .../final-smoke exit 0; services healthy and resources returned actual data with honest gap/unavailable metadata. Exact new-file inventory is in final-verification.json.

## Targeted throughput/recovery continuation — 2026-10-10 IST

This section supersedes only the current pending counts, not the failed soak.
The 25-asset/5-second/30-minute target remains FAIL/INCOMPLETE. No new soak,
image build, replay generation or earlier acceptance suite was performed.

### Storage, exact ledger and source activity

Preflight again confirmed develop and unchanged HEAD. C: had approximately
1.06 GiB free. All six H06 services were running. The H07 source/bridge were
already stopped, exit 137 with OOMKilled=false; neither was restarted. The
existing H06 single-asset source/bridge continued. Read-only SQL found database
size 58 MB, WAL 304 MB; later PostgreSQL data directory 552,248 KiB and Docker
data VHDX 11,900,289,024 bytes. These are size samples, not proof of the original
host disk depletion cause. No deletion, pruning or operator database access.

[Before reconciliation](evidence/h07/recovery/reconciliation-before.json) has an
individual disposition for **every one of the 4,450 expected asset/sequence/time
identities**. Its aligned event-window ledger is:

| At the recovery baseline | Count |
|---|---:|
| Committed at/before original measurement end | 756 |
| Committed after original measurement end | 38 |
| Pending, with no committed SQL receipt | 1,131 |
| Expected sequence absent from both SQL and spool | 2,525 |
| Total | 4,450 |

The 2,525 are explicitly `UNACQUIRED_EXPECTED_SEQUENCE`, not successful delivery
or an invented broker drop count. The source advances every asset in five-second
event steps, exposing only the newest register snapshot. Observed later sequence
numbers and the bridge's missed-snapshot counters corroborate skipped acquisition
between polls. There is no individual generator emission audit; these entries
have no captured payload/hash or exact emission wall time. Per-emission physical
production totals therefore remain unverified. Their scheduled identities are
enumerated; no historical measurements were fabricated to recover them.

The entire stopped spool covers a longer interval than the measurement window:
**2,050 acquired = 803 receipt-confirmed removals + 1,247 pending**. SQL held 819
accepted pairs, because 16 of the pending entries were already committed but not
yet checked. There were 125 acquired identities outside the measurement window.
PUBACK counter 2,088 is acknowledgment attempts including retries, not distinct
records. Of pending entries, 16 had attempts/PUBACKs and reason NOT_YET_COMMITTED;
1,231 had attempts=0, no PUBACK and no disposition reason yet. All were PENDING,
none quarantined. Historical unique-published counts for removed rows are not
retained and cannot be reconstructed from the global PUBACK counter. Per-asset
rejection/drop counters and precise broker/backend in-flight totals remain
unavailable. Details: [identity inventory](evidence/h07/recovery/spool-identities-before.json),
[counter definitions](evidence/h07/recovery/pending-counter-definitions.json).

### Measured bottleneck and bounded correction

A read-only container profile restored an actual checkpoint, exported it and
prepared/discarded an observation; it never installed state or wrote SQL.
[Primary profile](evidence/h07/recovery/readonly-profile.json): 609 history rows,
7,406,357 JSON bytes, SQL/registry read 0.242 s, import 3.612 s, export 1.139 s,
prepare 2.455 s under cProfile (7.202 s, 15.5 million calls). Serialization and
deep copies dominate. A [portfolio profile](evidence/h07/recovery/readonly-profile-portfolio.json)
with 36 rows/302,931 bytes took SQL read 0.055 s, import 0.177 s, export 0.056 s,
prepare 0.260 s. Profiling overhead is included; these are diagnostic stage
measurements, not an unbiased full transaction benchmark.

[Checkpoint sizes](evidence/h07/recovery/checkpoint-sizes.jsonl) subsequently
showed primary 7.885 MB, including 6.199 MB identity-cache results and 1.658 MB
canonical history. The backend creates a private session and validates/imports
the full durable checkpoint per transaction, then transfers committed state to
the owner. It also previously exported the same full checkpoint twice merely
to read its timestamp and transfer it after install. That redundant work is
concretely identified; it is not inferred from dashboard p95 alone.

The narrow fix in `backend/app/services/transactional_ml.py` reuses the exact
imported checkpoint for the timestamp and exact persisted candidate checkpoint
for post-commit transfer. All import/version/hash validation, SQL commit before
install, discard on rollback, asset locks, history and duplicate semantics remain.
`backend/tests/test_h02_transactional_adapter.py` adds a regression forbidding
redundant exports and comparing resulting checkpoint bytes/content, including
batch speculation and trip latch. Command from backend:
`python -m pytest tests/test_h02_transactional_adapter.py -q --tb=short`:
**6 passed**, exit 0, one Starlette deprecation warning. This is unit evidence,
not PostgreSQL proof; the real recovery below supplies SQL evidence.

The old live backend file was saved as
[transactional_ml-before.py](evidence/h07/recovery/transactional_ml-before.py).
Only the corrected backend module was copied into the existing disposable
container and `docker compose -p transformer-h06-20261009 restart backend`
executed. Actual installed ML package and all other services were retained;
readiness returned 200 with DEMO_UNVERIFIED_CONFIG. This was a targeted live
filesystem patch, not a rebuilt immutable image. A future clean image build must
include the checked-in source change when disk headroom permits. Current container
and source match; the old image tag alone does not contain this correction.

Other measured limits: bridge acquisition and delivery share a serial loop;
`flush()` checks one earliest entry per asset and can block acquisition behind
many receipt requests. This explains missed register snapshots as delivery grows.
The single ML owner remains CPU-bound by full-history work. Making acquisition
independent or compacting cached historical results requires a larger design/
compatibility review and was not attempted. SQL pool waits, exact per-transaction
SQL/commit duration and original disk-write attribution were not independently
instrumented. PG samples showed idle/idle-in-transaction clients, not proof that
there is never pool contention. Spool was only about 2.85 MB at peak; receipt
PUBACK timings do not indicate a slow broker as the dominant measured stage.

### Existing-record recovery and performance evidence

The existing DeliveryWorker, DurableSpool and ReceiptClient ran in an owned
helper sharing the **same** stopped H07 spool, with no acquisition. Host storage
was observed every two seconds with an abort guard of **768 MiB**, above the
512 MiB original safety threshold. No entry was manually removed/expired;
ordinary receipt-confirmed `DurableSpool.committed` transitions are the only
removals. No semantic payloads or hashes changed.

The first helper launch failed on a wrong mounted config path, preserved in
`recovery-measurements.jsonl`; mount inspection corrected `/app/config` to
`/config`. The next run confirmed **375** more receipts. Its nominal 300-second
loop ran **502.156 s** because a serial flush overran the loop deadline. The
330-second host monitor finished before that final flush; its samples do not
cover the entire run. Subsequent free-space checks remained above the guard,
but this is a real test-driver limitation, not a claimed precise 300-second test.
The helper exited 0, source remained stopped. The driver was corrected to one
eligible head per flush, fixed selection of assets 01/02/03, a 30-second bounded
test and a separate 45-second host stop deadline. That run completed in
**30.208 s**, confirmed **19** further receipts (0.629/s), and generated no data.
The first run's confirmed rate was 375/502.156 = **0.747/s**, including 16 receipts
already present at its start. Neither is a 25-asset cadence-capacity proof.

[Recovery timings](evidence/h07/recovery/recovery-summary.json), first attempt:
1,079 publish attempts, PUBACK latency p50 0.826 ms/p95 1.504 ms/max 1.146 s;
2,525 receipt checks p50 10.856 ms/p95 168.139 ms/max 8.055 s. For 359 identities
with both observations, first observed PUBACK to committed receipt confirmation
p50 9.486 s/p95 18.122 s/max 330.659 s. This uses actual observation wall times,
never historical event timestamps. It is confirmation latency, not independently
instrumented SQL commit time. Aggregate retry/backoff and serial queueing are
included. The three-asset recovery test does not claim fresh Modbus acquisition
or dashboard-visible latency; new generation testing stays NOT RUN.

At `2026-10-09T20:35:47Z`: acquired remains **2,050**, PUBACK attempts **3,204**,
receipt-confirmed removals **1,197**, retained pending **853**. SQL contains
**1,215** pairs, including **18** pending entries whose receipts have committed.
Every initial pending hash is either in SQL with matching accepted/hash fields
and exactly one telemetry/analytics pair, or still explicitly pending; no
unexplained acquired identity. SQL checkpoint observation counts match analytics
counts for all 25 assets. [After-window ledger](evidence/h07/recovery/reconciliation-after.json):
756 original-cutoff commits + 434 later commits + 735 pending + 2,525 unacquired
expected sequences = 4,450. SQL/spool snapshots are time-scoped, not one synthetic
instant spanning ongoing primary traffic. Pending recovery is **incomplete**.

### Fresh receipt identity diagnosis and final dispositions

The original failed helper did not save its probe hashes; those exact original
identities cannot be retroactively identified. This missing evidence remains
explicit. `simulator/scripts/demo_trace.py` now saves each actual probe's hash,
event time, sequence, observation time and receipt before its existing assertion;
its five-attempt assertion and receipt semantics were not weakened.
The same command was rerun only for this diagnosed receipt delay, writing
[trace-attempts.json](evidence/h07/recovery/primary-trace/trace-attempts.json).
It again exited 1 at the receipt assertion.

All five captured identities have HTTP 404, no SQL row and a matching pending
primary spool entry. Last example:
`cfbba7bcf5e560fca5937f854be267160c0b34f9ce9bbd5e8bc5d08f88da7cf0`, asset
H06-SIM-05, sequence 1562, event `2026-10-09T02:05:10Z`, observed
`2026-10-09T20:32:43.536363Z`. Its retained status is pending, not lost, conflicted
or committed. The backend and broker are running; the primary bridge reported
182 pending entries and a connected source at 20:33:07Z. New captured timeout
is a forward backlog delay, with exact dispositions in recovery-summary.json.
The primary current-receipt gate remains **FAIL/unresolved**. Its fixed historical
event clock is never used as a wall-clock latency subtraction.

Final C: free bytes were **957,472,768** (about 913 MiB). No further sustained
writes/load were justified with this small headroom and measured recovery rate.
Owned helpers exited/stopped and their containers/logs remain retained; the H07
source/bridge remain stopped. The six H06 services remain running, actual ML
mode retained. No volume, database row, image, source or prior evidence deleted.

PASS: aligned identity ledger, matching SQL pairs/checkpoint counts, partial
receipt-confirmed recovery, six focused regression tests, restored backend
readiness and bounded three-asset existing-record test. FAIL: original 25-asset
target and new current-primary receipt assertion. BLOCKED/incomplete: complete
backlog recovery and confident capacity run until adequate storage/throughput;
exact original timeout hashes and per-emission audit are unavailable. NOT RUN:
new full soak, fresh generated three-asset load/browser latency, immutable image
rebuild and larger state/acquisition redesign. An automatic approval-review
timeout affected one read-only inspection command; its single permitted retry
succeeded, with no safety rejection or outstanding permission request.

Additional changed paths in this continuation: backend adapter/test above,
trace helper, `simulator/scripts/h07_readonly_profile.py`, `h07_reconcile.py`,
`h07_recover_spool.py`, `h07_recovery_results.py`, this report, acceptance/runbook
updates, and files under `evidence/h07/recovery/`. Earlier H00–H06 reports,
contract, ML algorithms/state protocol, Compose and frontend remain untouched.

Final continuation validation:15 actual python -m json.tool commands exited0, zero failures; Python AST and all added Markdown links passed. Scope hash comparison found only the declared integration/config/adapter/test/trace paths changed against the original pre-H07 inventory; no earlier report or ML/frontend/Compose hash changed. Exact recovery evidence inventory and verification results are in [continuation-verification.json](evidence/h07/recovery/continuation-verification.json). All six primary services remain running; recovery helpers exited and resources are retained.


## 2026-10-10 continuation — preservation and targeted optimization (in progress)

This section preserves the earlier failed/incomplete soak. No new 30-minute
acceptance run has yet passed. Current branch is `develop`, HEAD
`29dcfaf5e12ef50446d1106c4994a721dc802476`; prior dirty work remains preserved.

A non-destructive backup at `D:/TransformerDigitalTwin-H07/20261010-preservation`
contains a custom PostgreSQL dump, consistent SQLite backups, retained service
logs and a MQTT/spool archive. `pg_restore --list` and a complete
`pg_restore --file=/dev/null` stream read succeeded; no database was restored or
reset. SQLite integrity checks passed. The live MQTT archive is a preservation
copy, not a claimed quiesced atomic broker backup. Backup manifests include
SHA-256 values. Additional consistent spool snapshots have per-file hashes in
[identity reconciliation](evidence/h07/20261010-diagnosis/20261010T081454Z-reconciliation.json).

Initial C: free was 7,195,078,656 bytes; D: free 178,421,010,432 bytes.
Docker reported images 3.991 GB, build cache 4.998 GB, volumes 725 MB.
Later [storage snapshot](evidence/h07/20261010-diagnosis/current-storage.json)
shows build cache 4.999 GB and volumes 1.373 GB. No caches, images, volumes,
pending records or existing database records were deleted. The original
transient disk decline cannot be attributed retrospectively to one writer;
current image/cache totals dominate storage and PostgreSQL/WAL growth also
matters. New load requires at least 5 GiB C: free; generation aborts at 4 GiB.

Receipt-only recovery confirmed all 2,050 originally acquired portfolio hashes:
spool acquired=2,050, committed=2,050, pending=0, PUBACK attempts=4,546.
The first corrected helper recovered 729 entries in 600.232 seconds; the
remaining 124 recovered in 194.922 seconds including the intervening outage.
All 475 acquired hashes of the new 90-second diagnostic run also confirmed:
committed=475, pending=0, PUBACK attempts=988; its final recovery took 266.388 s.
These are receipt-confirmed transitions through the existing worker, not manual
spool deletion. Pending source payloads/hashes were unchanged. All five saved
primary trace hashes now have matching COMMITTED receipts and one telemetry /
analytics pair each. Original uncaptured probe hashes remain unknowable.
Primary ongoing backlog remained 393 entries at 08:14:54Z and is still being
recovered, with a readable backup and individual pending dispositions.
The original 2,525 expected-but-unacquired sequences were not regenerated;
old generator logs lack per-emission hashes. They remain explicit acquisition
loss/unknown exact emission evidence from the failed run.

The 90-second bounded run [soak-b41b39](evidence/h07/soak-b41b39/manifest.json)
completed generation but FAILED throughput: 214 SQL rows at elapsed 84 seconds,
194 pending at that sample. Final source/bridge audit acquired 475 identities,
zero missed snapshots, 234 receipt confirmations and 241 pending at stopping.
This command's completion exit 0 is not a performance PASS.

Measured checkpoint costs prompted narrow changes: native JSON scalar dispatch;
private immutable history/identity entry sharing while copying mutable lists and
component state; immutable serialized identity-cache bytes with fresh checkpoint
JSON trees; a fully validated warm-owner cache invalidated by PostgreSQL row
`xmin` revisions (any content edit forces full validation); cold-only SQL
history hydration; independent acquisition and receipt-delivery threads with
serialized durable SQLite operations; base-interval polling for healthy 404
receipts, retaining exponential transport-failure backoff; opt-in per-identity
audit records and graceful owned-source stopping. No algorithm, physical unit,
model release gate, hash rule, checkpoint format or commit/install boundary was
changed. Checkpoint SQL remains in the accepted observation transaction.

Passed focused checks: 34 executed session tests (the initial module inherited
and discovered the baseline twice; subsequent selection avoids this); 5 narrowly
selected serialization/restart/isolation tests; 22 generator/register tests;
17 concurrency/delivery/real-loopback FC04 tests; 8 adapter unit tests;
4 actual PostgreSQL transaction/resource tests; then 11 adapter/real PostgreSQL
revision-corruption/rollback/batch tests. The revision test proves a same-header
checkpoint content edit cannot reuse the cached owner. Unit mocks are not the
PostgreSQL evidence. PostgreSQL tests used newly created isolated test databases,
never reset the retained demo database.

Intermediate failures retained: initial helper inherited the simulator CLI and
rejected `python` (corrected with `--entrypoint python`); generator test collection
was blocked by missing jsonschema (installed 4.26.0 into isolated test dependency
path, rerun passed); one patch used a wrong cwd-relative path (no edits occurred,
corrected); the new receipt-poll test initially lacked a valid snapshot identity
(corrected to the existing canonical generator fixture); strict recovery attempt
[da0bc08d](evidence/h06/container/strict-recovery-da0bc08d.json) failed its pre-retry
queue-settling barrier while receipt-only recovery traffic was active. Its retry
is in progress after those helpers finished. This is not yet a strict-gate PASS.

The optimized container is currently patched in place from reviewed source;
existing container logs and volumes are retained. A small simulator overlay
`simulator/Dockerfile.h07` reuses the established installed image; no dependencies
or unrelated images were rebuilt. Fresh ordinary backend packaging includes the
changed source. Full load remains NOT RUN pending bounded performance and
strict-recovery results. H07 remains incomplete.


## 2026-10-10 final continuation — full soak BLOCKED by capacity and user decision

This dated finding supersedes the in-progress status above without erasing the
failed attempts. The user explicitly chose **“Keep the full soak blocked and
document the findings.”** No new 30-minute run was started. H07 remains
**FAIL / INCOMPLETE**, with the next full run **BLOCKED**. The 25-asset target
and p95 <10-second target have not been lowered or met.

### Preservation, disk and final reconciliation

At the final read, C: free was **4,718,833,664 bytes (4.39 GiB)** and D: free
178,225,545,216 bytes. C: is below the enforced 5-GiB starting guard; emergency
stop is 4 GiB. No further generation, replay, rebuild or recovery helper was
started after this decision. The retained H06 primary remains running; this
is not a claim that its continuing backlog is fresh or fully drained.

Docker Desktop's data disk is
`C:/Users/Amitosh Nigam/AppData/Local/Docker/wsl/disk/docker_data.vhdx`
(13,007,585,280 bytes). Images total 3.991 GB, build cache 4.999 GB, local volumes
1.392 GB, container writable layers 24.69 MB. PostgreSQL observed database size
205,560,855 bytes, checkpoint relation 155,090,944 bytes and WAL 1,073,741,824
bytes. These are differently timed snapshots, not additive categories or a
monotonic growth series. Windows pagefile was 17,559,269,376 bytes; initial
pagefile size is unknown, so it cannot be blamed retrospectively for the space
loss. Physical free memory was about 1.6 GB on the 16-GB i7-13620H laptop;
Docker's memory limit was 7.606 GiB. Images/cache and database/WAL occupy substantial
space; the exact writer responsible for the sudden last C: decline is unresolved.
No cache, image, volume, log, pending entry or user database was pruned/deleted.

[Final consistent spool backups and SQL reconciliation](evidence/h07/20261010-diagnosis/20261010T084847Z-reconciliation.json)
were captured at **08:48:47Z**. Each backup passed SQLite integrity checks and
has a SHA-256 recorded there. The initial custom PostgreSQL preservation dump
is readable both by listing and complete decompression; no restore/reset was
performed. The live broker archive is not an atomic quiesced backup.

| Spool at that snapshot | Acquired | PUBACK attempts | Receipt-confirmed counter | Retained entries | Already SQL committed within retained entries |
|---|---:|---:|---:|---:|---:|
| Original portfolio dfb1b1 | 2050 | 4546 | 2050 | 0 | 0 |
| Bounded b41b39 | 475 | 988 | 475 | 0 | 0 |
| Bounded 1ea791 | 200 | 281 | 64 | 136 | 16 |
| Ongoing primary | 3161 | 6496 | 2975 | 186 | 1 |

Thus all original **853 pending entries, including the 18 awaiting receipt
checks, recovered through actual receipt-confirmed worker transitions**. All
five saved primary trace hashes have exact COMMITTED receipts and one telemetry /
analytics pair each. The primary's newer pending entries are a separate backlog.
For the 180-second run, 80 acquired identities have SQL receipts, 64 have been
confirmed by its stopped worker, 16 are committed awaiting checks, and 120 remain
durable pending without SQL receipts. None is relabelled delivered on PUBACK.
The 186 primary entries and 136 stopped bounded-run entries are retained and
individually classified; receipt recovery is deferred, not discarded.

The original 4450 expected observations reconcile as **756 committed inside the
measurement interval +1169 committed afterward +2525 scheduled-but-unacquired**.
The complete acquired count 2050 includes 125 outside the original cutoff.
[Original sequence ledger](evidence/h07/recovery/reconciliation-20261010.json)
retains every expected sequence's classification. The 2525 absent events were
not regenerated. The old source did not audit emission hashes, so actual emission
versus missed register acquisition cannot be established retrospectively. This
remains a failed acquisition gate, not successful recovery of all expected events.

### Measured bounded results and remaining bottleneck

[Computed measurements](evidence/h07/20261010-diagnosis/final-bounded-measurements.json)
use nearest-rank percentiles of matching selected-asset DOM/API observations,
with live-clock event timestamps. They are sparse browser samples, not proof
that every event became visible or a representative full-soak distribution.

| Run | Measured interval UTC | Duration | Audited source snapshots including setup/stop | SQL committed at final query | Visible unique samples | Event-to-visible p50 / p95 / p99 |
|---|---|---:|---:|---:|---:|---|
| b41b39 | 07:38:43.581971–07:40:13.582384 | 90.0004 s | 500 | 475 | 22 | 34.210 / 49.728 / 51.862 s |
| 1ea791 | 08:24:25.864797–08:27:25.872554 | 180.0077 s | 1125 | 80 | 6 | 31.852 / 39.595 / 39.595 s |

There were 450 and 900 source event timestamps respectively inside the actual
measurement windows. The 90-second run had 25 setup snapshots not acquired;
its 475 acquired snapshots ultimately all committed. The 180-second run acquired
only 200 of its 1125 logged source snapshots: 80 committed, 120 retained pending,
925 not acquired/no SQL or spool. These counts include source work before/after
the window and must not be substituted for the 900 in-window expected events.
Per-hash ledgers preserve the distinction:
[90-second identities](evidence/h07/soak-b41b39/final-identity-ledger.json),
[180-second identities](evidence/h07/soak-1ea791/final-identity-ledger.json).
The real SQL check confirmed matching accepted hashes and exactly one telemetry
and analytics pair for every receipt found; no missing acquired identity is
unexplained. Unacquired source snapshots remain an explicit performance loss.

Browser errors were 1/23 and 6/12 observations; browser exit codes were 0 and 1.
Driver exit 0 records completed measurement, **not performance acceptance**.
At 84 seconds the first run had 214 SQL rows (about 2.55/s versus required 5/s).
The second run's receipt-confirmed count was 64 (about 0.36/s over 180 seconds,
not a steady-state capacity estimate). API timeout samples are unavailable
measurements, not zero persisted rows. Recorded HTTP maxima included energy
100.905 s, telemetry 70.268 s, maintenance 57.961 s and registry 55.910 s.

The second run's 200 acquisition audit samples had event age p50 9.569 s,
p95 10.605 s, max 11.196 s before delivery. Receipt attempts recorded 281 PUBACKs
and 64 receipt confirmations. Received-to-visible p95 was 8.813 s for the first
run and 18.615 s for the second. Exact publish-to-SQL-commit timing is unavailable:
server receipt timestamps use transaction time and are not a measured commit
instant; confirmation audit shows successful post-commit observation. First-run
per-publication audits were not enabled. Queue, memory and storage samples are
retained in each measurements JSONL, not interpolated across failed API requests.

Profiling identifies expensive full checkpoint decoding/exporting and SQL
checkpoint writes, plus acquisition blocked behind sequential receipt delivery.
The narrow changes below remove redundant work while retaining post-SQL-commit
installation. After warm caching, 100-record stage samples averaged 0.0029 s
checkpoint read/restore, 0.5765 s preparation and **1.2174 s checkpoint SQL**,
with 92 warm reuses. The primary checkpoint was about 16.49 MB, containing 2853
identity entries and 668 historical rows. Cold imports still cost several
seconds. This checkpoint growth/write cost remains unresolved. A rolled-back
pglz/lz4 comparison was diagnostic only; no database compression setting changed.
Windows memory pressure, API contention and scheduler delays also coincided with
the second test; their individual contribution is not isolated. Frontend polls
only the selected asset, but changing event-dependent callbacks may amplify
requests. Neither speculative parallel backend workers nor untested history/
identity retention changes were introduced. Sustainable 25-asset capacity has
not been established.

### Changes and commands actually exercised

Changed implementation paths in this continuation:

- `ml/pipeline/session.py`, `ml/tests/test_session_h07.py`.
- `backend/app/services/transactional_ml.py`, `backend/app/services/ingestion_service.py`, `backend/app/repositories/processing_repo.py`.
- `backend/tests/test_h02_transactional_adapter.py`, `backend/tests/test_h02_postgres.py`.
- `simulator/simulator/spool.py`, `simulator/simulator/modbus_bridge.py`, `simulator/simulator/modbus_server.py`, `simulator/tests/test_h07_concurrent_spool.py`.
- `simulator/Dockerfile.h07`, `simulator/scripts/demo_portfolio.py`, `simulator/scripts/h07_recover_spool.py`, `simulator/scripts/h07_preserve_and_reconcile.py`.
- `simulator/config/analytics-policy.json`; `simulator/config/h07-b41b39/server.json`, `bridge.json`; `simulator/config/h07-1ea791/server.json`, `bridge.json`.
- This report, `ACCEPTANCE_RESULTS.md`, `DEMO_RUNBOOK.md`, and dated evidence files under `evidence/h07/20261010-diagnosis/`, `soak-b41b39/`, `soak-1ea791/`, `recovery/`, plus the two strict-recovery JSON attempts under `evidence/h06/container/`.

Private immutable identity/history reuse returns independent result/checkpoint
JSON. PostgreSQL xmin is an internal revision token: changed/corrupt durable
content forces validation even with unchanged checkpoint headers. Cold-only
history hydration preserves restart semantics. SQLite operations are serialized;
a separate delivery worker prevents receipt waiting from blocking acquisition.
Healthy 404s poll at the base interval; transport errors retain bounded exponential
backoff. Hashes, algorithm outputs, checkpoint schema and SQL commit/install order
are unchanged. Opt-in audits expose actual emission/acquisition/PUBACK/receipts.

**PASSED:** focused session encoder/rollback/restart selection (5 tests); adapter
and real PostgreSQL revision/rollback/batch selection (11 tests); additional
four real PostgreSQL transaction/RUL/energy projection tests; concurrency/delivery/
real FC04 tests (17); generator/register tests (22). Commands included
`python -m pytest tests/test_h02_transactional_adapter.py` from backend,
targeted `tests/test_h02_postgres.py::test_checkpoint_revision_reuses_owner_but_detects_content_edit`
and its transaction cases using disposable test databases, and selected
`python -m unittest` session tests. The earlier 34-test discovery duplication is
reported above, not added to unique coverage.

`python simulator/scripts/demo_container_failures.py --recovery-only` ultimately
**PASSED**, [aafa90c1](evidence/h06/container/strict-recovery-aafa90c1.json): real
broker interruption, identity-scoped pending receipt checks, durable restart,
matching hash `2f4f3b428cd906fb2dd4fbd13410fbbfe565e1a4cbe0b6c4ed83a3e883d6a374`,
exactly one pair and idempotent retry. This command proves broker recovery;
it is not a newly executed database-outage test. SQL injected rollback/restart
was tested separately against PostgreSQL.

`python simulator/scripts/h07_preserve_and_reconcile.py --backup-dir D:/TransformerDigitalTwin-H07/20261010-preservation`
and `python simulator/scripts/h07_reconcile.py 20261010` exited 0. Existing
receipt-only helpers exited 0 for final original/90-second recovery. Docker
Compose status, read-only SQL and saved audit analysis succeeded.

**FAILED:** intermediate strict attempt da0bc08d while recovery traffic prevented
its barrier settling; missing-jsonschema initial collection; initially invalid
new test identity; first helper entrypoint invocation. Corrections and passing
reruns are retained. Both bounded portfolio performance tests failed target;
the second browser run failed. Source/bridge stop logs include connection-refused
polls after stopping the source, and second-run containers exited 137 after the
bounded Docker stop timeout. This leaves a shutdown responsiveness limitation;
durable pending entries and logs are preserved.

**SKIPPED / NOT RUN:** full earlier phase suites were not repeated. The requested
narrow H05 regression command
`python -m unittest ml.tests.test_rul_h05 ml.tests.test_energy_h05 ml.tests.test_pipeline`
did not start: automatic approval review timed out; it was not denied on safety
grounds. No test result is claimed. A retry was deferred when disk/RAM margin
became unsafe. Fresh human teammate rehearsal remains NOT RUN.

**BLOCKED:** full 25×5s×30-minute soak (C: <5 GiB and explicit user decision),
remaining 180-second pending recovery and final current-primary fresh receipt
acceptance, and capacity/latency closure. Authentic fitted artifacts remain
unavailable; the actual runtime uses visibly DEMO_UNVERIFIED_CONFIG. No empirical
RUL accuracy, operational fault-risk release or real-equipment claim is made.

All six H06 services remain running; database, broker, API, frontend and simulator
health checks report healthy. All H07 load sources/bridges and recovery helpers
are stopped, retained with their data/logs. No full acceptance rerun occurred.
Further work requires safe disk headroom, bounded testing that actually achieves
throughput, then a genuinely measured full run. H07 is **not ready for final
acceptance**. No commit, push, merge or next phase was performed.

Final documentation validation: three actual `python -m json.tool` commands exited0; all14 changed Python files parsed successfully with `ast.parse`; all added local Markdown links resolved. [Validation evidence](evidence/h07/20261010-diagnosis/final-documentation-validation.json). These lightweight checks do not replace deferred runtime acceptance. Branch remains `develop`.
