# Acceptance results â€” evidence, not blanket approval

Date: 2026-10-10. Tested develop HEAD 29dcfaf5e12ef50446d1106c4994a721dc802476
with the reviewed local implementation. PASS is scoped to the named observation;
remaining subcases are marked separately. No live transformer, fitted accuracy,
operational lifetime or official organizer performance claim is made.

## Integrated acceptance cases

| Case | Status | Concrete evidence and scope |
|---|---|---|
| A01 clean actual Python/container runtime | PASS | [H06 report](H06_RUNTIME_AND_SINGLE_ASSET_INTEGRATION.md): six-service fresh setup, installed ML, PostgreSQL16 migrations0001â€“0004 and 13 actual SQL tests. H07 baseline script succeeded without rebuilding. |
| A01 strict fitted artifacts | BLOCKED | [H01 report](H01_ML_RUNTIME_AND_STATE.md): original permitted artifacts unavailable. Explicit DEMO_UNVERIFIED_CONFIG is the actual runtime. |
| A02 canonical validation/source/time | PASS | [H02 report](H02_BACKEND_CONTRACTS_AND_TRANSACTIONAL_STATE.md) focused schema evidence and H06 real PostgreSQL contract tests; H07 registered fictional verified-as-synthetic configuration and aware source times. |
| A03 actual FC04/registerâ†’SQL/API/DOM | PASS | [H06 container trace](evidence/h06/container/modbus-sql-trace.json) and [browser](evidence/h06/container/browser.json); current H07 primary rehearsal evidence in its report. No writes. |
| A04 MQTT/durable receipts | PASS | [H06 strict gate](evidence/h06/container/strict-recovery-4121588e.json): observable outage, post-outage pending identity, exact hash/SQL receipt and no repeated effects. H07 uses actual broker/bridge. |
| A04 invalid/torn/mismatch | PASS | H03 focused protocol tests and H02 topic validation tests reported in their phase evidence; not all these fault variants were rerun through every live UI. |
| A05 transaction/idempotence/conflicts | PASS | [H06 failures](evidence/h06/container/failures.json), strict gate and 13 PostgreSQL tests: exact retry, HTTP/MQTT conflict, injected SQL failure/rollback and retry. |
| A06 staged state/restart/metadata | PASS | H01 checkpoint tests and H06 real PostgreSQL rollback/restart evidence; single-worker owner enforced. |
| A06 complete one-hour thermal readiness | BLOCKED | Sparse H06 pre-roll and unverified model/unit prerequisites do not establish full feature readiness. H07 30min alone cannot establish one-hour history; metadata remains honest. |
| A07 API React / switching | PASS | H06 actual React/browser evidence; H07 judging-switch uses delayed actual response JSON and verifies selected asset identity/snapshot, without fixture fallback. |
| A07 real API-stop/error/last-success | PASS | [Actual backend outage/DOM](evidence/h07/soak-dfb1b1/judging-outage.json): unchanged last-success, disconnected and retained stale data; backend restored. |
| A08 synthetic RUL / operational null | PASS | [H05 report](H05_RUL_AND_ENERGY_ANALYTICS.md) deterministic80h/zero/no-crossing/insufficiency and checkpoint tests; H06 APIs/browser actual80h and gated real-source null. |
| A09 bounded energy/reset/units | PASS | H05 arithmetic tests, [H06 actual API oracles](evidence/h06/container/api-oracles.json)20kWh/5kWh/reset13covered and unsupported full total null. |
| A10 eligible fictional loss/equal service | PASS | H05 pure oracle90.9091% and equal-service comparison; integration keeps losses/efficiency null without required physical boundary inputs. No measured saving claim. |
| A11 rated overload/trip/effects | PASS | H03 physical coherence tests plus H07 controlled asset01 event-time timeline and SQL trip rows, independent neighbors. |
| A11 thermal divergence fully ready | BLOCKED | Complete validated thermal model/coverage eligibility is not established; unavailable status is displayed. |
| A12 replay lineage/isolation | PASS | Native canonical replay accepted two original events; [actual replay DOM](evidence/h07/soak-dfb1b1/judging-replay.json) shows REPLAYED, historical time and separate origin/run. Prior H05 state/speed isolation evidence retained. |
| A13 registry/provenance/nameplate | PASS | H02/H06 real PostgreSQL registry, nullable additions and tests; all H07 ratings labelled SYNTHETIC_CONFIG. |
| A14 broker/SQL recovery | PASS | H06 actual container failure and strict broker gate evidence; no destructive reset. |
| A14 source interruption/recovery | PASS | [Bounded actual FC04 interruption/restoration](evidence/h07/soak-dfb1b1/source-interruption.json); API outage browser passed separately. Independent per-unit restart and invalid-quality browser rehearsal NOT RUN. |
| A15 25 assets5s30min / target latency | FAIL | [Measured partial soak](evidence/h07/soak-dfb1b1/summary.json): 891.56 seconds, safety disk stop, 756/4450 within-window commits; p95 live-event-to-visible age 381.826 seconds. Exact acquisition timing unavailable. |
| A16 executable commands/runbook | PASS | Resource/replay/browser commands executed; [runbook](DEMO_RUNBOOK.md). Fresh current-snapshot trace timed out with backlog: that subcase FAIL. |
| A16 fresh human teammate rehearsal | NOT RUN | A teammate who did not implement it has not yet independently followed this final runbook. Manual team review remains required. |

## P0/P1 finding closure

| Finding | Status | Evidence/remaining scope |
|---|---|---|
| F01/P0 API-backed dashboard | PASS | H04 client/components and H06 actual DOM/API; H07 switching/outage observations. |
| F02/P0 real runtime primary | PASS | H06 installed package/image/topology and current health check. |
| F03/P0 reproducible strict fitted release | BLOCKED | Authentic fitted artifacts missing; honest explicit demo mode is installed and proven, not fitted readiness. |
| F04/P0 metadata survives backend | PASS | H02 persistence tests, H06 actual JSON and H07 per-asset data. |
| F05/P0 RUL delivered | PASS | H05 synthetic method and nullable operational eligibility; H06 resources/curve and80h real DOM. |
| F06/P0 Modbus demonstrated | PASS | Independent real FC04 trace, actual MQTTâ†’SQL receipt and read-only configuration. |
| F07/P1 energy analytics | PASS | H05 numerical/coverage/reset/unknown-unit rules and H06 API/React proof. Physical measured losses remain unavailable. |
| F08/P1 unsupported claims removed | PASS | H04 report/tests and actual UI; no new accuracy/performance/savings/compliance claims. |
| F09/P1 verified nameplate semantics | PASS | Nullable registry/provenance and gated eligibility; real physical nameplate evidence remains unavailable. |
| F10/P1 coherent abnormal simulation | PASS | H03 coherence tests and H07 configured overload/trip source with persisted isolation evidence. |
| F11/P1 canonical replay | PASS | H03 canonical adapter/JSONL and H05 event-time invariance; current fallback execution outcome recorded separately. |
| F12/P1 durable reliable delivery | PASS | H06 strict outage/receipts; H07 bounded spool retains load backlog instead of pretending completion. Capacity target separate. |
| F13/P1 durable isolated state | PASS | H01 staging/history and H06 SQL recovery; full thermal readiness still blocked as A06 states. |
| F14/P1 changed identity conflict | PASS | H00 hash rules, H02/H06 real SQL exact retry/conflict and actual MQTT rejection. |
| F15/P1 integrated validation | PASS | Actual single-asset container/SQL/API/browser path demonstrated; all-suite/portfolio blanket acceptance is not claimed. |

F16 portfolio capacity FAILED the measured target as P2 and must be reported independently;
F17 safety remains local/read-only, F18 loader compatibility is proven in H01,
F19 null/unit/source evidence is preserved, and F20 runbook human rehearsal stays
NOT RUN until the teammate executes it. All prior phase evidence retains its date
and scope; later real integration resolves previous infrastructure blockers rather
than rewriting those historical reports.

Current H07 single-asset resource checks PASS; new current FC04-to-receipt correlation FAIL (bounded receipt timeout). Historical H06 A03 proof is retained, not relabelled as a new successful H07 trace. See [H07 report](H07_PORTFOLIO_AND_JUDGING_REHEARSAL.md) for commands, intermediary failures and final state. Overall portfolio/judging acceptance remains incomplete.

## Targeted throughput/recovery continuation

| Case | Result | Evidence |
|---|---|---|
| Expected sequences classified | PASS with limitation | [Before ledger](evidence/h07/recovery/reconciliation-before.json):756 cutoff commits,38 later,1131 pending,2525 scheduled-but-unacquired. No individual emission audit/hash for unacquired frames. |
| Acquired pending hashes accounted for | PASS | [Recovery summary](evidence/h07/recovery/recovery-summary.json): matching SQL hash/one pair or retained pending; checkpoint counts match analytics, isolated trip state retained. |
| Narrow checkpoint export optimization | PASS | Six focused adapter tests including rollback/batch/duplicate/exact checkpoint transfer; actual SQL recovery separately evidenced. |
| Complete backlog recovery | BLOCKED/incomplete | 394 further receipt confirmations;853 pending remain,18 already committed but awaiting spool checks. |
| Fresh primary receipt | FAIL | Five captured identities still pending;HTTP404/no SQL. [Trace](evidence/h07/recovery/primary-trace/trace-attempts.json). Original unlogged hashes unavailable. |
| Fixed three-asset existing-record test | PASS scoped | 19 receipts in30.208s;768MiB disk guard/45s host deadline. No new generated-load/browser capacity claim. |
| Full25/5s/30min target | FAIL / no new run | Original failure retained; recovery0.747/s and scoped0.629/s do not prove capacity. |
| Updated immutable image | NOT RUN | Targeted backend module copied into disposable container and restarted; future build must include source fix when disk permits. |

H07 remains incomplete; partial recovery does not pass portfolio/current-result acceptance.


## 2026-10-10 correction and final capacity decision

These results supersede the preceding continuation's pending counts; prior
failures remain historical evidence. See the [dated H07 final continuation](H07_PORTFOLIO_AND_JUDGING_REHEARSAL.md)
and [final measured results](evidence/h07/20261010-diagnosis/final-bounded-measurements.json).

| Case | Current result | Actual evidence / limitation |
|---|---|---|
| Original 853 acquired pending entries | PASS | Original spool acquired=committed=2050, pending=0, receipt-confirmed worker transitions; readable backups preserved. |
| Five saved primary trace hashes | PASS | Exact committed receipt hashes, one telemetry/analytics pair each; original uncaptured identities remain unknown. |
| Original expected 4450 observations delivered | FAIL | 756 cutoff +1169 later commits +2525 unacquired expected sequences. Missing events not regenerated. |
| Strict broker-outage gate after changes | PASS | aafa90c1 actual broker recovery, durable restart, receipt/hash/one pair; da0bc08d intermediate failure retained. |
| SQL rollback/restart/cache invalidation | PASS | Focused actual PostgreSQL tests including changed xmin/content; candidate not installed before commit. |
| 90-second performance / p95 <10s | FAIL | 22 visible samples, p95 49.728s; acquired475 eventually all committed, not full-run capacity. |
| 180-second performance / p95 <10s | FAIL | Browser exit1; 200 acquired,80 SQL committed at final query,120 durable pending;6 valid visible samples p95 39.595s. |
| Remaining new bounded backlog | BLOCKED | 136 retained entries:16 SQL committed awaiting checks,120 without receipt; no pending data deleted. |
| Ongoing primary fully fresh/drained | BLOCKED | At08:48:47Z186 retained entries,one SQL-committed overlap; historical H06 proof remains valid. |
| New full 25 assets /5s /30min | BLOCKED | C:4.39GiB below5GiB guard; user explicitly requested keep blocked. Previous 14m52s target remains FAIL/INCOMPLETE. |
| Complete dashboard visibility / bounded resources | FAIL | Sparse observed values do not prove all events visible; severe API latency and checkpoint growth remain. |
| Fresh human teammate rehearsal | NOT RUN | Final manual review still required. |

No full portfolio acceptance is claimed. Existing P0/P1 single-asset evidence is
retained with its original scope; it does not close the failed capacity gate.
