# H07 — Verify portfolio isolation and rehearse the judging demonstration

## AI CODING AGENT PROMPT

You are implementing one authorized phase of the Transformer Digital Twin on `develop`. Inspect the listed files and necessary imports/tests only; do not re-audit the repository. Read the phase prerequisites and the relevant F findings in `../GAP_ANALYSIS.md` (relative to this prompt). Verify the current branch and local changes before editing. Preserve teammate changes; stop on an ownership conflict rather than overwriting them. The planning baseline is develop `71c1b27200b91f3933c52692748935f4a62d63e8`; newer code requires a narrow relevant delta check.

Implement only the work below. Do not commit, push, merge, touch `main`, retrain existing models, rewrite valid thermal/anomaly/HI/maintenance algorithms, change frontend stack, or write to real transformer/protection controls. Do not change excluded canonical fields or turn missing values into zero. Preserve existing tests and honest null operational forecast. New future CLI/API paths below are implementation targets, not claims that they exist today.


### Objective, owners, gaps and prerequisites

Owner: Person 4 runs portfolio/load rehearsal; Person 2 observes persistence/latency/state and signs backend evidence; Person 3 verifies browser; Person 1 signs truthful analytics/limitations. Depends H06. Addresses F16/P2, F17/P2 local safety, F20/P2 final runbook correctness and final F15/P1 readiness evidence. H03 built scheduler and H04 built registry-driven portfolio; this phase verifies them, not a second implementation of either.

Inspect only H06 configs/scripts and execution reports, per-asset generator/session paths, frontend portfolio client, backend status/receipts and `../INTEGRATION_AND_DEMO_ACCEPTANCE.md`. Read open questions for physical-data restrictions. Application edits here are limited to small diagnosed load/integration defects in owned components with owner coordination, not new scope or algorithms.

### Work and expected outputs

1. Execute single-asset suite first, then 25 fictional configured ids on actual Modbus unit ids with isolated RNG/energy/scenario/thermal/history/checkpoints. Proposed team target is 5s per asset, 30min soak, p95 acquisition-to-visible-current-result <10s for live-clock simulation. Record actual hardware, versions, rates, received/committed/conflict/drop counts, row coverage, peak memory/queue/spool, API and browser latency; these are engineering targets, not organizer requirements. Accelerated historical replay uses separate playback metrics, never negative latency from past/future event timestamps.
2. Inject trip/overload/missing register into one asset and prove neighbors' telemetry, HI, alerts, RUL/degradation and energy unaffected. Switch UI rapidly while delayed responses return. Stop/restart one source, broker, bridge and backend; test stale indication, recovered checkpoint/spool and exactly-once application effects despite QoS1 duplicates. Preserve existing SQL conflict rejection.
3. Rehearse primary and labelled fallback scripts exactly; save a brief correlated register→SQL→API→DOM trace and actual command outputs with timestamps, no credentials. Record fitted versus demo-unverified model mode; no fabricated model score or real-life RUL. Add `docs/hackathon_readiness/execution/DEMO_RUNBOOK.md`, `ACCEPTANCE_RESULTS.md` and requirement checklist linking actual evidence. Correct only current runbook defects; audit remains dated evidence.
4. Default network bind stays loopback; configured source kind is explicit. Mark live connection disabled pending operator authorization/OEM map/units/ratios. No real writes, no production reset, no unsupported compliance or 25-live-connection claim. A synthetic threshold crossing does not establish actual physical safety trip performance.

### Acceptance, verification and fallback

Run `bash simulator/scripts/demo_25.sh`, `bash simulator/scripts/demo_check.sh` after H06 creates/verifies them, plus affected focused regression suites. Browser observation required for selected-asset and status display. Integrated acceptance table must mark every case PASS/FAIL/BLOCKED with command/evidence, not all green by default. One successful Modbus proof is mandatory even if rehearsal falls back to HTTP. If laptop capacity fails the proposed soak target, report actual sustainable count/cadence, preserve a complete single-asset judged path, and classify 25-stream target unmet rather than claiming 25 connections. Do not lower targets silently.

Done when the clean setup and realistic demo script can be executed by a teammate who did not write it, all P0/P1 closure evidence is linked or explicitly blocked, and every displayed RUL/energy/model/source claim matches actual evidence. Numerical algorithm tests are reused unless a load fix changes their behavior. Stop after final execution report and runbook; do not commit, deploy publicly, seek live access or create another phase.


### Completion report and stopping point

Report phase ID, changed paths, contract/version changes, actual commands and outcomes (passed/failed/skipped separately), unmet acceptance criteria, remaining inputs, and the exact next dependent phase. Include one concrete input/output example and any regression or integration evidence. Do not claim unavailable infrastructure tests passed. Update the phase execution evidence in `docs/hackathon_readiness/execution/` with a new phase-specific report; do not overwrite audit evidence. Stop after this phase's assigned outputs and focused checks. A blocked gate stays blocked; do not begin another phase or silently substitute stub results.
