# Prioritized gap analysis

Evidence refers to the pinned snapshot in [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md). Implemented code is not automatically trained, integrated or validated. Acceptance thresholds below are proposed engineering demo criteria, not organizer judging weights.

Severity: P0 blocks the complete required demonstration or its credibility; P1 materially weakens correctness/readiness; P2 supports robustness, scale or handoff; P3 cosmetic/optional polish. No separate P3 item outranks the gaps below.

## F01 — Dashboard bypasses backend analytics

- Severity / owner: **P0**, Frontend.
- Exact location: [`frontend/src/components/InteractiveTwinStudio.tsx`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/frontend/src/components/InteractiveTwinStudio.tsx#L4), `runTwinSimulation`.
- Evidence and missing behavior: useMemo calls local runTwinSimulation and local history generator. No fetch/axios/WebSocket/EventSource ingestion client exists in frontend/src. App is a single-page presentation with anchor sections, not a connected monitoring application.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Keep existing visual components; add a canonical API client and render backend latest/history/alerts/maintenance. Move scenario selection to a simulator command boundary.
- Dependencies: F02, F03, F04.
- Acceptance criteria and tests: Insert a uniquely identifiable row via HTTP and MQTT; selected asset dashboard must show the same timestamp and values as GET latest within the proposed 10-second demo target. Backend failure, null fields, empty history, and stale telemetry must be visible.


## F02 — Compose runs stub and cannot load the ML package as packaged

- Severity / owner: **P0**, Integration.
- Exact location: [`docker-compose.yml`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/docker-compose.yml#L59), `ML_BACKEND: stub`.
- Evidence and missing behavior: Compose explicitly selects stub. backend/Dockerfile copies only backend app/package and dependencies; no ml package, numpy/pandas/scipy/sklearn or fitted bundle is included. Compose has no frontend service and references backend/.env, absent in a fresh checkout.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Package the tested ML entrypoint with its dependencies and artifact/configuration manifest, select ml.pipeline:analyze, document .env creation, and serve the existing frontend. Do not simply change the environment switch without packaging.
- Dependencies: F03, F04.
- Acceptance criteria and tests: Fresh checkout startup uses actual ML, reports its version/mode, survives a deliberate model failure while storing telemetry, and serves frontend. Protection fixture gives ML HI=0/URGENT; stub outputs never appear as validated ML.


## F03 — Fitted release cannot be reproduced from checkout

- Severity / owner: **P0**, ML release.
- Exact location: [`ml/pipeline/bundle.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/pipeline/bundle.py#L50), `load_from_processed_dir`.
- Evidence and missing behavior: Root data/ is absent and ignored. ML README lists fitted artifacts and hashes, but all 26 release tests error on missing data/processed/release_manifest.json. Loader silently uses coded defaults on missing or malformed thermal/anomaly files and still returns processed_bundle_v1/model_version 1.0.0.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Obtain existing raw/processed bundle and manifest from ML owner, verify hashes, and provide a reproducible download/build procedure or explicit labelled demo-configuration mode. Report missing/corrupt artifacts, avoid an apparently fitted identity.
- Dependencies: ML owner artifact access.
- Acceptance criteria and tests: Release tests pass with authentic files; missing/corrupt artifacts return an explicit configuration/unverified state. Reproduce claimed thermal metrics before publishing them. Do not restart all phases.


## F04 — ML explanations and readiness are lost at backend boundary

- Severity / owner: **P0**, Contract.
- Exact location: [`backend/app/ml_client/base.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/backend/app/ml_client/base.py#L63), `extra_keys`.
- Evidence and missing behavior: parse_ml_result drops unknown top-level keys, including metadata. ML metadata carries thermal_readiness, source unit/mode, coverage, extended reasons and forecast status; analytics schema/ORM lack it. REJECTED_LATE_OBSERVATION violates the two-value inference_status enum and becomes generic insufficient-data failure.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Agree on additive versioned component-status/evidence metadata; persist and expose it consistently. Map late observations to a supported explicit ingestion outcome rather than suppressing the reason.
- Dependencies: Backend/ML contract agreement, migration.
- Acceptance criteria and tests: Serialize real UnifiedMLPipeline output through Python client, ORM and latest/history API; readiness, units, coverage and null-risk reason survive. Late row retains an explicit sequencing explanation. Existing score names and enum meanings remain compatible.


## F05 — Required RUL deliverable is absent

- Severity / owner: **P0**, RUL.
- Exact location: [`ml/evaluation/engine.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/evaluation/engine.py#L309), `rul_prognostics`.
- Evidence and missing behavior: Code only declares RUL not estimable/organizer requirement unresolved. There is no ageing/RUL algorithm, API/ORM output or dashboard view. User now confirms RUL mandatory. The workbook has no lifetime targets.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Add a clearly labelled simulated degradation first-passage demonstration and insufficient-data operational contract; enable thermal-ageing estimates only with verified prerequisites. Retain existing HI as operating condition.
- Dependencies: RUL method choice, F04, F09.
- Acceptance criteria and tests: RUL card/API returns units, method, provenance, uncertainty/range and assumptions. Missing baseline life or hot-spot parameters yields null with reason. Simulated trajectory reaches its declared threshold and demonstrates repeatable remaining time; no HI-to-years conversion or empirical accuracy claim.


## F06 — Required Modbus demonstration is missing

- Severity / owner: **P0**, IoT.
- Exact location: [`simulator/pyproject.toml`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/simulator/pyproject.toml#L6), `dependencies`.
- Evidence and missing behavior: No Modbus server/client, register map, bridge, pymodbus dependency or Compose service exists in the audited source tree. MQTT consumer and simulator publisher exist.
- Hackathon impact: Blocks a credible complete-system demonstration.
- Proposed correction: Extend existing simulator with Modbus TCP read interface and a read-only register-to-canonical-to-MQTT bridge. Retain MQTT backend consumer.
- Dependencies: Register map, F02, F04, F09.
- Acceptance criteria and tests: Independent client reads known encoded values and alarm bits; bridge decodes same snapshot and persists one canonical row, then dashboard displays it. Demonstrate disconnect, invalid register/scale and recovery. Captured read requests establish Modbus use.


## F07 — Energy telemetry exists but useful analytics and display do not

- Severity / owner: **P1**, Energy.
- Exact location: [`simulator/simulator/generator.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/simulator/simulator/generator.py#L148), `self._energy_kwh +=`.
- Evidence and missing behavior: Generator integrates active kW at fixed configured interval; backend stores power/energy and can return generic trends. No interval-energy/reset/coverage/loss/efficiency service or dashboard energy view exists. Frontend energy is a constant 124850.5 and is not an implemented consumption calculation.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Add measured-counter and calculated-power integration strategies, source unit verification, coverage and reset segmentation, load profile and bounded conservation scenario comparison.
- Dependencies: F04, F09, F11.
- Acceptance criteria and tests: Known 10 kW over covered 2 h gives 20 kWh; duplicates add nothing; long gaps are excluded; reset creates a new segment; measured and estimated energy are distinct. Loss/efficiency unavailable without input data. Savings shown only as scenario estimates.


## F08 — Presentation makes unsupported performance and physical claims

- Severity / owner: **P1**, Frontend evidence.
- Exact location: [`frontend/src/components/ImpactMetrics.tsx`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/frontend/src/components/ImpactMetrics.tsx#L8), `Predictive Lead Time`.
- Evidence and missing behavior: Static +48h lead time, -74% outage reduction, <15ms inference and 100% contract-compliance claims have no inspected measurement evidence. README claims IEEE C57.91 and 48h warning; local model is an instantaneous heuristic and local fault_risk=1-HI/100, confidence=0.92.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Replace with substantiated metrics or labelled design goals/demo outputs in a later change. Render fault forecast unavailable until release gates pass; do not call local categorical scenarios physical fault diagnoses.
- Dependencies: F01, F03, team presentation review.
- Acceptance criteria and tests: Every numeric performance claim links to a reproducible evaluation/benchmark with denominator and provenance, otherwise removed/labelled proposed. Unreleased risk renders null and reason. Demo labels remain visible in screenshots.


## F09 — Nameplate configuration is incomplete and lacks verification semantics

- Severity / owner: **P1**, Asset registry.
- Exact location: [`backend/app/models/transformer.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/backend/app/models/transformer.py#L19), `rated_power_kva`.
- Evidence and missing behavior: Registry CRUD exists for rating/voltages/current/cooling/oil. No frequency, vector group, impedance, temperature-rise limits, side, CT/PT ratios, verification/source/effective date or insulation metadata. Any positive rating is used without a verification flag. AssetConfig aliases voltageHvKv into rated_voltage_hv without conversion; schema V/kV is ambiguous.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Extend existing registry and migration with explicit volts, side/phase count and provenance; separate fictional simulation config from verified asset config. Collect asset-specific thermal/loss parameters only as needed.
- Dependencies: Nameplate/organizer evidence, F04.
- Acceptance criteria and tests: Round-trip a verified and a simulated asset with all required fields; kV-to-V conversion is explicit; invalid non-positive rating rejected; missing/unverified rating withholds operational loading/RUL. 50 A test setting never becomes rated current.


## F10 — OVERLOAD does not necessarily overload and injection breaks energy consistency

- Severity / owner: **P1**, Simulator physics.
- Exact location: [`simulator/simulator/faults.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/simulator/simulator/faults.py#L223), `def _inject_overload`.
- Evidence and missing behavior: Injection multiplies present load by 1.3–1.4 rather than targeting rated load. Focused 20-row probe with seed 42 at midnight produced only 34.844–52.992% of fictional 500 kVA. Power changed 127.27 to 171.89 kW while energy remained 2.12 kWh. Voltage/current-imbalance injections also do not recompute power consistently. Thermal update alpha=0.05 per sample ignores configured interval duration.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Drive scenarios from declared per-asset load/configuration and a physical state transition; recalculate coupled power/reactive/energy after final scenario state; use elapsed-time thermal update.
- Dependencies: F09, simulator scenario ownership.
- Acceptance criteria and tests: OVERLOAD exceeds declared rating throughout intended scenario; balanced power/current consistency holds within documented tolerance; energy integrates final power; subdividing the same forcing interval yields consistent thermal state. Labels describe simulated conditions.


## F11 — Separate replay adapter omits power fields and diverges from ML adapter

- Severity / owner: **P1**, Replay.
- Exact location: [`simulator/simulator/schema.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/simulator/simulator/schema.py#L100), `SOURCE_TO_CANONICAL`.
- Evidence and missing behavior: Replay source mapping lacks KW/KVA/KVAR/KWH while ML adapter maps them. Minimal timestamped KW=10/KVA=12/KVAR=6/KWH=100 CSV probe returned all power/energy null. Outer merge before duplicate resolution can multiply rows and discards _dup columns without conflict diagnostics. WTI is cast as a generic numeric value.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Reuse ML canonical adapter output for replay, preserving its WTI conflict policy, source time and quality diagnostics. Support already-canonical timestamped replay.
- Dependencies: ML adapter interface, verified units/timezone.
- Acceptance criteria and tests: Replay an adapter fixture with duplicate timestamps and conflicting WTI; output agrees with canonical adapter including power, missingness and conflicts. No Cartesian duplication or WTI-as-temperature display; unknown timezone is explicit.


## F12 — Delivery and startup are not reliable enough for a demonstrable stream

- Severity / owner: **P1**, Streaming.
- Exact location: [`simulator/simulator/cli.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/simulator/simulator/cli.py#L182), `999_999`.
- Evidence and missing behavior: Default unlimited stream generates 999,999 records into memory before publishing. HTTP publisher catches HTTP errors and CLI still increments sent/prints published. MQTT fallback is selected only at construction; later broker failure lacks durable retry/fallback. Consumer ACK precedes DB commit and queue overflow/crash can lose telemetry.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Generate incrementally, verify publication result, spool/retry bounded records with unique identity and persist diagnostics. Expose actual ingest acknowledgements and bridge/source lag; allow operator-selected fallback.
- Dependencies: F06, backend ingestion dedupe.
- Acceptance criteria and tests: First record appears without million-row allocation; forced broker/backend outage produces explicit disconnected state and bounded retained backlog; recovery/replay causes no duplicate analytics/energy. HTTP 500 is never reported as success.


## F13 — Backend supplied history is ignored and state is not durable

- Severity / owner: **P1**, ML state.
- Exact location: [`ml/pipeline/orchestrator.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/pipeline/orchestrator.py#L539), `def analyze(`.
- Evidence and missing behavior: Public analyze accepts history but never uses it; singleton state is memory-only. max_history_rows=60 gives about 5 minutes at 5-second cadence despite one-hour rolling features. State advances before SQL commit, and SQL rollback does not restore singleton state.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Choose one state owner: serialize per-asset state or reconstruct from bounded time-based history/checkpoints under a lock; tie state commit to accepted telemetry/analytics. For demo use a single ML owner process and deliberate warm-up after restart.
- Dependencies: F02, F04, concurrency policy.
- Acceptance criteria and tests: Restart yields replay-equivalent results or explicit reinitialization; 1 h features use documented covered history at 5s and 15min cadence. Inject failed DB commit and retry, with no latch/state advancement lost or duplicated. Asset threads cannot mix state.


## F14 — Changed same-time telemetry silently receives stale analytical result

- Severity / owner: **P1**, Idempotency.
- Exact location: [`ml/pipeline/orchestrator.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/pipeline/orchestrator.py#L196), `if ts == state.last_processed_timestamp`.
- Evidence and missing behavior: process_record returns last_result whenever timestamp matches without comparing payload. Focused probe changed oil_temp_trip from 0 to 1 at same timestamp and returned identical HI=100/NORMAL. Backend telemetry insert likewise keys identity/time and ignores duplicate payload changes.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Keep retries idempotent for identical payloads, but reject/quarantine conflicting same-key payloads or explicitly revise with ordered reanalysis policy.
- Dependencies: F13, payload hashing and ingestion policy.
- Acceptance criteria and tests: Identical retry changes no state; changed trip at same key returns conflict, never silently healthy. Record conflict counter/raw evidence. Different assets at same timestamp remain independent.


## F15 — Live stack/database end-to-end remains unverified

- Severity / owner: **P1**, Validation.
- Exact location: [`backend/tests/conftest.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/backend/tests/conftest.py#L33), `TEST_DATABASE_URL`.
- Evidence and missing behavior: No Docker executable or running PostgreSQL test URL was available. 187 backend tests skip without PostgreSQL. Frontend builds and ML-to-client smoke passes, but neither establishes browser-to-database-to-ML flow.
- Hackathon impact: Can invalidate results or interrupt the demonstration.
- Proposed correction: Run existing PostgreSQL migrations, integration tests and primary/fallback demonstration on team machine; capture versioned run results.
- Dependencies: F01–F06 and team runtime.
- Acceptance criteria and tests: Existing DB tests execute without unintended skips; fresh migration/reset/replay/alert lifecycle work; complete Modbus-to-dashboard trace includes source/asset/time/version. Save startup and outage demonstration evidence.


## F16 — Multi-asset primitives exist but 25-asset demonstration does not

- Severity / owner: **P2**, Multi-asset.
- Exact location: [`ml/pipeline/state.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/pipeline/state.py#L21), `AssetPipelineState`.
- Evidence and missing behavior: Backend registry/asset-scoped telemetry keys and ML per-asset states exist; frontend has three static unrelated assets, simulator CLI one transformer id per invocation. MQTT publisher default client id is shared across processes. No measured 25-asset capacity or portfolio visualization.
- Hackathon impact: Limits reproducibility, scale or truthful interpretation.
- Proposed correction: Reuse registry, isolated generators/injectors/model states and unique publisher identities; add 25-asset scheduler/portfolio overview.
- Dependencies: F01, F09, F12, F13.
- Acceptance criteria and tests: 25 simulated asset ids each produce distinct streams and scenario/state. Proposed target: 5s cadence, 30min run, zero cross-asset contamination, p95 acquisition-to-display <10s, recorded actual latency/drop counts. Clearly say 25 simulated assets.


## F17 — Local demo boundaries must precede authorized live use

- Severity / owner: **P2**, Security/provenance.
- Exact location: [`backend/docs/known-limitations.md`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/backend/docs/known-limitations.md#L19), `General API endpoints`.
- Evidence and missing behavior: API lacks general authentication; Compose anonymous MQTT and local demo credentials are bounded to localhost. is_demo_mode treats mqtt generically as demo, so real MQTT acquisition would need separate provenance. Future remote live connection is not configured/verified.
- Hackathon impact: Limits reproducibility, scale or truthful interpretation.
- Proposed correction: Keep demo isolated; before live monitoring use operator authorization, network allowlist, read-only Modbus access, MQTT ACL/TLS, explicit source kind and device mapping. Do not write protection/control registers.
- Dependencies: Asset/operator authorization, F06, F09.
- Acceptance criteria and tests: Live profile denies unauthorized ingress/writes and distinguishes live versus simulated MQTT. Device/topic id mismatch rejected. Credentials never appear in dashboard/log evidence.


## F18 — Forecast artifact writer/loader schema mismatch

- Severity / owner: **P2**, ML packaging.
- Exact location: [`ml/pipeline/bundle.py`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/ml/pipeline/bundle.py#L110), `pe.get("preprocessor"`.
- Evidence and missing behavior: Writer emits top-level preprocessing, loader reads primary_experiment.preprocessor. With writer-shaped artifact preproc_dict stays empty and predictor remains None. Silent catch masks other loading errors. Operational risk remains correctly gated null.
- Hackathon impact: Limits reproducibility, scale or truthful interpretation.
- Proposed correction: Align artifact schema in a narrow repair and verify round-trip without enabling unvalidated risk.
- Dependencies: F03, artifact schema version.
- Acceptance criteria and tests: Writer-shaped fixture loads frozen feature order/scaler/coefficient state; invalid file has a diagnostic; experimental score is labelled, operational risk remains null absent release eligibility.


## F19 — Null, unit and simulation semantics drift across workstreams

- Severity / owner: **P2**, Contracts/UI.
- Exact location: [`frontend/src/types.ts`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/frontend/src/types.ts#L19), `CanonicalTelemetry`.
- Evidence and missing behavior: Frontend raw telemetry/components are non-null types; backend accepts nullable fields and normalizes protection to ints. UI adds OPTIMAL state and percent oil/°C WTI; public WTI is explicitly status in ML adapter. Frontend HI weights 25/20/15/15/15/10 differ from ML 30/20/10/15/20/5, and frontend current divides rated line current by sqrt(3) again.
- Hackathon impact: Limits reproducibility, scale or truthful interpretation.
- Proposed correction: Generate/maintain API-boundary types with null/status support and explicit unit metadata; remove client analytic duplication, keep isolated educational simulation distinctly labelled. Correct line/phase current convention in demo.
- Dependencies: F01, F04, F09.
- Acceptance criteria and tests: Partial API response renders unavailable, never zero or normal; WTI status never °C, unknown oil unit never %. API HI/maintenance match view. Known balanced rating satisfies I=1000S/(sqrt(3)V_LL).


## F20 — Existing phase/release documents are out of date for present requirements

- Severity / owner: **P2**, Documentation.
- Exact location: [`docs/implementation/AUDIT_PLAN.md`](https://github.com/Amitosh07/Transformer-digital-twin/blob/c7d12df6feeb7bb076bc9fac6151e3dd10c2670e/docs/implementation/AUDIT_PLAN.md#L9), `RUL`.
- Evidence and missing behavior: Master describes an earlier inaccessible repository snapshot; README claims completed phases and unavailable RUL requiring confirmation. Current code exists, RUL now confirmed required. DEMO_RUNBOOK uses HEALTHY status incompatible with backend and unsupported adapter CLI arguments; ML README analyze example has unsupported asset_config signature.
- Hackathon impact: Limits reproducibility, scale or truthful interpretation.
- Proposed correction: Treat existing phases as historical plans; add precise correction notes/real supported commands in future without rewriting tested methodology. This audit supersedes readiness claims only for pinned commit.
- Dependencies: F03–F05, team documentation owner.
- Acceptance criteria and tests: Fresh teammate can reproduce supported entrypoint/startup and explain unavailable forecasts/RUL. No file:/// local Windows links or incorrect HEALTHY enum in new handoff. Existing documents preserved during Part 1.
