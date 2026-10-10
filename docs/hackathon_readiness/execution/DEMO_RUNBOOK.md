# Local judging demonstration runbook

Date: 2026-10-10 (Asia/Calcutta). Branch develop, HEAD
`29dcfaf5e12ef50446d1106c4994a721dc802476` plus the reviewed uncommitted H00Ã¢â‚¬â€œH07
worktree. All sources are fictional SIMULATED or explicitly REPLAYED; real
acquisition is disabled. Runtime mode is DEMO_UNVERIFIED_CONFIG; fitted release,
operational fault risk/lifetime and unverified loss/efficiency remain unavailable.

## Prerequisites and safe preparation

Use the existing disposable project `transformer-h06-20261009`. Docker Desktop
and its Linux engine, Python with installed approved ML/simulator packages and
psycopg, and Git Bash are required. Browser rehearsal uses installed Edge and
playwright-core under the existing temporary h06-browser dependency directory.
The temporary browser dependency is a test driver, not dashboard data.

PowerShell, repository root:

```powershell
$env:COMPOSE_PROJECT_NAME='transformer-h06-20261009'
$env:PYTHONPATH="$env:TEMP/h06-test-dependencies"
docker compose ps
Invoke-RestMethod http://127.0.0.1:8001/health/ready
& 'C:/Program Files/Git/bin/bash.exe' simulator/scripts/demo_check.sh --evidence-directory docs/hackathon_readiness/execution/evidence/h07/baseline
```

Use Git Bash rather than the WindowsApps WSL `bash` launcher. Equivalent Git Bash
commands are `export COMPOSE_PROJECT_NAME=transformer-h06-20261009` then
`bash simulator/scripts/demo_check.sh --evidence-directory docs/hackathon_readiness/execution/evidence/h07/baseline`.
Use a new evidence directory for another rehearsal; preserve previous evidence.
A fresh checkout/container installation follows [H06 runbook](../../../simulator/H06_RUNBOOK.md)
and its configuration example; do not rebuild an already healthy rehearsal.
Never delete/reset volumes or overwrite an operator .env. Fresh setup was proved
in H06; an independent human teammate rehearsal remains a separate acceptance item.

## Services and source identities

| Service | Loopback host port | Container endpoint |
|---|---|---|
| PostgreSQL 16 | 55433 | db:5432 |
| Mosquitto | 51885 | mqtt:1883 |
| Backend, actual installed Python ML | 8001 | backend:8000 |
| React/Nginx | 5173 | frontend:80 |
| H06 read-only FC04 simulator | 1502 | modbus-simulator:1502 |
| H07 portfolio simulator during a run | 1503 | run-specific source:1502 |

Only FC04 reads are used. Protection contacts are output/status, never controls.
H06 primary asset is H06-SIM-05, map fictional-lv-v1, unit 1 and gateway H06-DEMO-GW.
Historical fixed-UTC H06 events deliberately show stale event time despite recent
API polls. H07 uses unique run-specific H07 IDs, separate source/bridge/spool and
live-clock time. It registers fictional configuration and adds only those new
asset policies; existing policies are preserved. No real ratings or units are inferred.

## Primary presentation

```powershell
& 'C:/Program Files/Git/bin/bash.exe' simulator/scripts/demo_primary.sh
python simulator/scripts/demo_probe_modbus.py --host 127.0.0.1 --port 1502 --asset H06-SIM-05 --unit 1
& 'C:/Program Files/Git/bin/bash.exe' simulator/scripts/demo_check.sh --evidence-directory docs/hackathon_readiness/execution/evidence/h07/primary
```

Open http://127.0.0.1:5173 and select H06-SIM-05. Show source, event/analytics
times, bundle/configuration/readiness, actual HI/reasons and thermal unavailable
states where coverage is insufficient. Show the actual degradation curve and
scenario endpoint. H06-RUL-ORACLE demonstrates 80 h; H06-ENERGY-CONSTANT with
2h event window shows 20 kWh; H06-ENERGY-RAMP shows 5 kWh. These are labelled
fictional arithmetic scenarios, not all readings from the same Modbus stream.
Do not claim empirical lifetime or measured savings. A PUBACK is transport only;
GET /api/v1/ingestion/receipts/{snapshot} must show COMMITTED and matching hash.

## Portfolio measurement

```powershell
& 'C:/Program Files/Git/bin/bash.exe' simulator/scripts/demo_25.sh --duration-seconds 1800
```

Default is 25 assets, five-second source cadence and 1800 seconds. Any shorter
diagnostic interval does not satisfy the soak. The driver reuses the existing
scheduler/map/bridge image, publishes over actual MQTT, and reads actual SQL/API/
React responses. Only asset 01 has overload at event offsets 120Ã¢â‚¬â€œ150 s and trip
150Ã¢â‚¬â€œ180 s. Neighbors retain independent seeds, measurements, configuration rates,
checkpoints, energy and effects. No universal thermal threshold is introduced.
The measured run is stopped if host C: free space falls below 512 MiB; that
outcome must be reported as unmet capacity. Do not silently lower the target.

Evidence is written under evidence/h07/soak-{run-id}; configuration remains under
simulator/config/h07-{run-id}. The driver stops only its own source/bridge after
measurement and retains containers, records and durable spool. Pending records
are not described as committed. Do not restart a retained source with the same
identity casually: it restarts the deterministic timeline and must honor exact
retry/late/conflict semantics. Choose a new run for a new forward stream.

## Resilience and replay fallback

```powershell
python simulator/scripts/demo_container_failures.py --recovery-only
& 'C:/Program Files/Git/bin/bash.exe' simulator/scripts/demo_replay.sh --native
```

The strict outage test requires the established disposable project and retains
its bounded helper spool. It establishes real broker-offline conditions, accounts
for old receipts, and proves a new identity pending until its matching SQL receipt.
Replay uses the installed canonical CLI via the verified native flag and actual
backend; it is HTTP fallback, not Modbus proof. Destination H06-REPLAY-R1/run H06-R1
preserves H06-RUL-ORACLE origin and fixed source timestamps. Select it in React:
REPLAYED, simulated origin, historical event time/stale state must remain visible.

For browser switching/outage rehearsal use the actual generated manifest:

```powershell
node simulator/scripts/demo_judging_browser.mjs <manifest-path> switch
node simulator/scripts/demo_judging_browser.mjs <manifest-path> outage
node simulator/scripts/demo_judging_browser.mjs <manifest-path> replay
```

`outage` stops only disposable backend briefly, checks unchanged last-success and
visible disconnected/stale state, then starts it in finally. Run disruptive tests
after the soak, not inside a claimed uninterrupted measurement interval.

## Recovery and handoff

Inspect `docker compose ps`, `/health/ready` and bounded service logs first.
Restore only a stopped owned service with `docker compose start <service>`.
A PostgreSQL restart loses the single-worker advisory lease; restart only the
backend afterward. Do not run multiple independent ML workers for this demo.
Spool pending/conflict and consumer diagnostics remain visible; never clear a
spool to obtain a green result. Stop only named owned H07 containers when needed;
keep all volumes/data/images. Complete final review against [acceptance results](ACCEPTANCE_RESULTS.md),
including the recorded unmet capacity/coverage targets. No live equipment access
or public deployment is part of this runbook.

## Recorded capacity and limitations

The actual H07 25-asset attempt stopped after 891.56 seconds at the host disk
safety boundary. Delivery fell behind: 756 of 4,450 expected within-window
observations committed; p95 live-event-to-visible age was 381.826 seconds.
Do not claim the 30-minute/10-second target. Retained run dfb1b1 has 1,247
pending spool entries; they are not deleted or assumed delivered. The current
primary bridge also has backlog; the fresh bounded current-snapshot receipt
probe failed. Use the explicit historical H06 correlated trace as prior evidence,
not a replacement for a new successful rehearsal.

The browser script needs the temporary Playwright dependency installed in
`$env:TEMP/h06-browser`; if absent, create that test-only directory and install
`playwright-core@1.64.0` there using npm before rehearsal. Installed Edge is
required; this dependency path is a test-driver convention, not a runtime
package-path hack. The actual manifest for the recorded checks is:
`docs/hackathon_readiness/execution/evidence/h07/soak-dfb1b1/manifest.json`.
Replay freshness correctly says Historical replay, rather than current live
freshness. Inspect [H07 report](H07_PORTFOLIO_AND_JUDGING_REHEARSAL.md) before
repeating load. Stop an owned portfolio bridge/source by their exact names from
its manifest; leave their spool and data intact. Do not casually restart the
retained source timeline with reused IDs. No automated backlog-drain procedure
was proven here; plan bounded delivery recovery separately if needed.

## Targeted recovery continuation

Latest portfolio pending count is853, superseding1247 without erasing the original
failure. Free space at stop was913MiB; do not launch another soak/build/replay at
this margin. Existing DeliveryWorker/ReceiptClient recovered394 further receipts;
no manual record deletion or semantic identity changes. The recovery-only driver
`simulator/scripts/h07_recover_spool.py` uses the existing image with inherited
`/config` and `/spool`, internal Docker network and no other spool owner. It
acquires no Modbus data. Its corrected test is fixed assets01/02/03, one causal
head per flush,30-second duration,45-second host deadline and abort below768MiB.
The earlier25-head run overran its nominal deadline; do not reuse that loop.
A general full-drain procedure is not proven; plan storage/throughput before
attempting one. Retained helper names and exact results are in the phase report.

The backend source fix reuses persisted checkpoints rather than exporting full
history twice. Six focused tests passed. Current disposable backend module
`/app/app/services/transactional_ml.py` was copied from local source and the
backend restarted without an image build or ML package change. The old module
is retained in recovery evidence. A future clean image build must include this
source fix; the old image tag alone does not. Preserve DEMO_UNVERIFIED_CONFIG
and single-runtime ownership. Current-primary receipt is still unresolved;
demo_trace.py now captures exact hash/sequence before its unchanged assertion.
Original unlogged hashes cannot be reconstructed. Never substitute health200
or a historical receipt for a fresh correlated result.


## 2026-10-10 capacity hold

Do not start another soak in the recorded state: C: has4.39GiB free, below the
5GiB starting guard, and the user chose to keep the full soak blocked. Emergency
stop is4GiB. All H07 sources/bridges are stopped; H06 services continue running.
Keep pending spools and all Docker/database resources. The dated H07 report
lists unresolved checkpoint/write and latency costs. Existing30-minute target
is not accepted. No pruning/reset command is a recovery prerequisite.

Read-only/preservation checks from the repository in PowerShell:

```powershell
$env:COMPOSE_PROJECT_NAME = 'transformer-h06-20261009'
Get-PSDrive C,D | Format-List Name,Free
docker compose ps
docker system df
python simulator/scripts/h07_preserve_and_reconcile.py --backup-dir D:/TransformerDigitalTwin-H07/20261010-preservation
```

The last command creates new timestamped consistent backups and queries receipts;
it does not delete spool entries. Use the existing readable backup directory or
a safe available destination. Read the identity ledger before deciding whether
a recovery helper may run. Do not treat PUBACK counters as committed counts.
Only reconsider load after sufficient disk margin and successful bounded
throughput tests; retain the original25/5s/30min and p95<10s requirements.
