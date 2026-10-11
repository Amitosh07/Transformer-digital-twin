# H05 — Synthetic RUL and evidence-gated energy analytics

Execution date: 2026-10-09. Implementation and deterministic analytics/state checks are ready for H06 consumption, subject to the integration limitations below. No empirical RUL accuracy or real transformer's remaining life is claimed.

## Baseline and scope

Before editing, `git branch --show-current` returned `develop`, `git rev-parse HEAD` returned `29dcfaf5e12ef50446d1106c4994a721dc802476`, and `git status --short` showed the existing uncommitted H00–H04 work. The complete status was inspected; 153 individual pre-existing changed/untracked files were recorded with SHA-256 hashes outside the repository. Final preservation verification found zero unexpected changes to those files; only the three necessary integration files listed below changed. Branch and HEAD remained unchanged.

H00 contract `1.1.0`, its fixtures and all earlier execution reports remain untouched. Backend, frontend, simulator, Modbus and root Compose were not changed. Existing ML algorithms, weights, artifact versions and forecast-release gates remain unchanged. No commit, push, merge, H06 or H07 work was performed.

Exact created paths:

- `ml/rul/__init__.py`
- `ml/rul/common.py`
- `ml/rul/config.py`
- `ml/rul/model.py`
- `ml/rul/types.py`
- `ml/rul/fictional_scenario_v1.json`
- `ml/energy/__init__.py`
- `ml/energy/config.py`
- `ml/energy/calculation.py`
- `ml/energy/loss.py`
- `ml/energy/types.py`
- `ml/tests/_h05_fixtures.py`
- `ml/tests/test_rul_h05.py`
- `ml/tests/test_energy_h05.py`
- `ml/tests/test_h05_session.py`
- `docs/hackathon_readiness/execution/H05_RUL_AND_ENERGY_ANALYTICS.md`

Exact narrowly changed pre-existing paths:

- `ml/pipeline/orchestrator.py`: additive RUL computation/component metadata and staged extension update after identity checks.
- `ml/pipeline/session.py`: validation of restored synthetic extension, configuration, curve and result consistency.
- `ml/pyproject.toml`: include the two runtime packages and fictional configuration JSON; add optional `h05-test` dependency `jsonschema==4.26.0`.

Generated wheel/build metadata were confined to temporary export directories for the final build. Earlier wheel-building outputs created inside `ml/` were removed only after confirming they were not pre-existing files. No raw data, notebooks or tests were added to the runtime wheel.

## Synthetic RUL and public interfaces

The method is `SYNTHETIC_FIRST_PASSAGE_V1`, model identity `synthetic-first-passage-v1`. The bundled scenario version is `fictional-rul-v1`; its asset-independent arithmetic parameters are explicitly fictional. It starts at `2026-10-09T00:00:00Z`, with dimensionless D=0.2, endpoint=1.0, rate=0.01/hour, horizon=100 hours, maximum observed gap=10 seconds, and declared rate bounds 0.008–0.012/hour. These are scenario parameters, not fitted artifacts or transformer life constants.

`SyntheticConfig` and `Duty` validate aware timestamps, finite nonnegative state/rates, positive endpoint/horizon, bounded future duty and explicit gap policy. `predict_synthetic(current, config, timestamp, acquisition, ...)` returns `RULProjection` with an exact H00 `rul` dictionary and separate projected curve. `first_passage` integrates bounded piecewise-constant future duty exactly. Constant rate produces `(endpoint-current)/rate`; a finite crossing beyond the horizon is unavailable. Scenario bounds are supported for ordered constant-rate variations only and labelled `SCENARIO_RANGE`, never confidence intervals. Future-duty timelines and constant-rate bounds cannot be combined without defining another explicit scenario policy.

Results distinguish `SIMULATED_ESTIMATE`, `END_THRESHOLD_REACHED` (zero hours), `NO_CROSSING_WITHIN_HORIZON` (null hours), and `INSUFFICIENT_DATA` (null hours plus missing inputs). Missing configuration/state/rate/horizon, invalid values, unsupported gaps and incomplete future duty remain explicit. An endpoint already reached returns zero without requiring future extrapolation. Low-rate bounds that do not cross within the horizon are withheld rather than represented as infinity.

The authoritative [H00 contract](../../contracts/hackathon-v1.1.md) and `rul.schema.json` do not define a `projected_curve` wire member and reject additional fields. Therefore the curve is exposed through `RULProjection.projected_curve` and persisted in the existing checkpoint extension payload. It is **not** added to the frozen RUL resource. H06 can consume the internal curve; exposing it in an API requires an explicitly agreed future interface rather than silently altering H00.

To opt an asset into synthetic degradation, supply the versioned configuration through `AssetConfig.additional_configuration['synthetic_rul']` (the existing asset adapter preserves this additional configuration). Eligibility requires a `SIMULATED` source, or `REPLAYED` with `origin_kind=SIMULATED`. A replay retains `source_kind=REPLAYED`, origin asset ID/run ID and source event time. A live/source-only replay never receives a numerical synthetic fallback. HI, anomaly score, WTI contact and operational risk are not converted into degradation.

The orchestrator preserves existing result fields and exposes additive `rul` on 1.1.0 records or explicit synthetic scenarios. Legacy 1.0.0 callers without such a scenario retain their existing exact top-level response shape. Existing `analyze(transformer, record, history)` remains usable and uses H01 hydration once; it does not replay supplied history on every retry.

## State, checkpoint and accepted-commit semantics

H01's existing `PipelineSession.prepare(asset, record)` stages a copy, returning candidate result/checkpoint. `install(candidate, database_committed=True)` remains the backend-controlled installation boundary; the ML layer does not observe or claim a SQL commit. `discard(candidate)` preserves the committed state. No second checkpoint protocol was introduced.

The existing `synthetic_degradation` state category contains a versioned payload with extension version `1.0.0`, complete scenario/configuration fingerprint, asset and source lineage, current D, start/last event times, last H01 semantic payload hash, covered seconds, gap count and projected curve. The H01 outer checkpoint/schema/state-category versions remain unchanged. Import validates the payload, scenario fingerprint/version, last accepted observation's time/hash/lineage, curve and stored result. Incompatible/corrupt extensions fail explicitly through H01 checkpoint quarantine; existing unresolved trip context is preserved.

Observed D advances using positive elapsed event-time hours and the declared historical rate. Future piecewise duty describes prognosis from the current event. By default a gap beyond the configured policy makes current D unknown and prevents a numerical RUL until deliberate reinitialization/migration. Explicit `assume_constant_rate_across_gaps` permits fictional integration through a gap and discloses that it is a scenario assumption, not sensor coverage. Scenario removal/change while state is active is rejected; H06 must explicitly migrate/reinitialize it rather than silently resetting it.

Tests prove discard preserves serialized committed checkpoint/result bytes, installation advances once, exact retries do not advance state, changed protection payloads conflict, late observations leave forward state untouched, compatible JSON checkpoint restart reproduces the next result/checkpoint, corrupt checkpoints reject, and two assets keep independent D and trip latches. Replay run/source changes cannot share active state. Speed-1 and speed-20 representations of the same accepted event-time trace produce identical degradation and energy results; these are deterministic trace tests, not a live replay/broker demonstration.

## Operational eligibility

`assess_operational_eligibility(evidence)` reports required inputs and `MISSING_VERIFIED_*` limitation codes. Evidence entries require explicit `VERIFIED` status, reference, valid value and applicable units. Requirements include a measured hotspot or validated hotspot model (DEG_C), liquid, insulation, justified ageing parameters, life budget (hours), prior age/exposure (hours), future duty and temporal coverage with an explicit required minimum. Measured hotspot evidence additionally requires source-verified hotspot semantics/units; binary WTI and oil-temperature surrogates are ineligible.

`operational_result` uses `THERMAL_AGEING_ELIGIBILITY_V1` and always returns null RUL with `OPERATIONAL_RUL_ESTIMATOR_NOT_IMPLEMENTED`. Even fully supplied eligibility evidence does not release a numerical life estimate: the optional conditional-life estimator is outside this phase's minimum scope. Existing physical inputs are not manufactured, alarm rows are not end-of-life labels, and probability/forecast gates remain unchanged.

## Pure energy calculations

`calculate_energy(records, transformer_id, window_start, window_end, EnergyConfig, ...)` returns the exact H00 energy resource. `analyze_energy(...)` additionally returns covered-duration-weighted `mean_power_kw` outside the wire dictionary. The caller supplies persisted canonical records and explicit aware event-time bounds; there is no SQL access or route/query-anchor resolution in ML.

Configuration requires version, authoritative `POWER` or `COUNTER` method and maximum gap. The default maximum window is seven days and record cap 250,000 (configurable with validation). Exceeding either rejects instead of silently truncating. Records are normalized with the existing H01 semantic hash rules, sorted by UTC event time, deduplicated exactly, and changed asset/time or snapshot payloads conflict. Asset mismatch, noncanonical fields, nonfinite values, invalid protection/PF values and incompatible source/run/map/side lineage reject. One boundary context record on each side may support an explicitly qualified interpolation policy.

Counter calculation requires known kWh units, eligible verification and explicit cumulative import/export semantics. It uses Decimal differences, preserving small increments on large integer counters. Negative jumps are excluded as resets unless a valid modulus and rollover reference are explicitly supplied; reset evidence overrides a possible rollover. Long gaps are excluded unless independent counter continuity evidence is declared. Counter readings are never summed. Partial window counter differences are not extrapolated/interpolated.

Power calculation requires eligible kW units and an explicit sign convention. Instantaneous samples use trapezoids only for supported positive intervals with both endpoints and elapsed time within maximum gap. Import/export zero crossings are split; import-only policy rejects negative values. Explicit interval-average-start/end semantics treat the declared average as constant over that interval, with no instantaneous profile/peak claim. Boundary interpolation is off by default; when explicitly enabled it is linear, qualified and limited to supported instantaneous intervals, never extrapolation.

The response separates `energy_method` (`MEASURED_COUNTER`, `CALCULATED_POWER`, `SIMULATED`, `UNAVAILABLE`) from `calculation_method` (`COUNTER_DIFFERENCE`, `TRAPEZOID`, `NONE`). Simulated input remains simulated; replay retains source/lineage and a simulated origin where applicable. Unknown/unverified units or source semantics cannot produce numerical kWh. Load-profile peaks are actual observed instantaneous power with their timestamps. Missing intervals, coverage fraction/seconds, resets, gaps and boundaries remain explicit. Excluded seconds are recoverable directly from the missing interval bounds; no undeclared H00 field was added.

Full-window consumption/import/export totals are returned only for complete supported coverage. Partial supported consumption is separately labelled `covered_consumed_kwh`, with `PARTIAL`, actual coverage and limitations; it is never presented as a complete window. The configured minimum adds a distinct deficiency reason, including when covered arithmetic remains useful. An export-only counter does not become import consumption. Counter and power totals are never added.

## Loss, efficiency and advisory evidence

`LossModel` requires explicit version, P0 and rated-load losses in kW, compatible rated current in A, measurement side, energized state, delivered-output boundary, and field-level configuration evidence. VERIFIED parameters require references; SYNTHETIC_CONFIG parameters are eligible only for synthetic source/origin. Applicable source current/power units and verification are also checked. Asset metadata can be converted with `LossModel.from_asset`; missing leaves remain unavailable.

The disclosed approximation integrates `P0 + rated_load_loss*K_I²` with phase RMS current and exact squared linear-current integration. Full coverage and supported delivered-power boundary are required. Estimated efficiency is `100*P_out/(P_out+loss)` on a 0–100 scale, with positive delivered power/denominator. Losses are modelled, not measured. Missing parameters, unverified boundary/current, unsuitable sign or incomplete coverage leave loss/efficiency null with limitations.

An operator-review advisory is emitted only for a configured contiguous sustained duration with both interval endpoints above eligible rated loading. Rating/configuration/source eligibility remains H01's authority. Gaps break the sustained duration. No automatic control, compliance claim or hardcoded savings percentage is emitted. Additional PF/imbalance/cooling policies are not invented without explicit thresholds/evidence.

The optional conservation comparison requires two fictional eligible loss models, same synthetic origin, delivered service, output boundary and horizon. It compares integrated loss energy; reducing useful delivered load is not counted as savings. The test baseline loss is 1 kW (P0=0.8, rated-load loss=0.2, current equal to declared rating); the alternative is 0.6 kW under the same duty. Across two hours and the same 20 kWh useful output, modelled loss falls from 2 to 1.2 kWh, yielding a clearly simulated 0.8 kWh opportunity. This is not measured savings.

## Concrete examples

Fictional synthetic RUL: D=0.2, endpoint=1, g=0.01/hour, horizon=100 hours and simulated acquisition produce `rul_status=SIMULATED_ESTIMATE`, `rul_value=80`, `rul_unit=h`, `simulated=true`, `model_version=synthetic-first-passage-v1`. Declared rate bounds 0.008–0.012 give approximately 66.6667–100 hours, `SCENARIO_RANGE`. Zero rate gives null/no crossing; D=1 gives zero/end threshold. A live source without life evidence gives null/insufficient data.

For two canonical simulated records at 00:00Z and 02:00Z with eligible active power 10 kW, configure `EnergyConfig(version='fictional-energy-v1', method='POWER', maximum_gap_seconds=7200, power_sign='IMPORT_ONLY_NONNEGATIVE')`. The resource returns `consumed_kwh=20`, `covered_consumed_kwh=20`, `coverage_seconds=7200`, `coverage_fraction=1`, `energy_status=AVAILABLE`, `energy_method=SIMULATED`, `calculation_method=TRAPEZOID`. Loss/efficiency remain null without a loss model. A linear 0→10 kW one-hour trace gives 5 kWh. Changing maximum gap to 10 seconds excludes that unsupported sparse interval instead of asserting 20 kWh.

Counter 100→110 within a supported hour gives 10 kWh via `COUNTER_DIFFERENCE`. 100→110→2→5 over three hours excludes the reset interval: complete consumption is null, supported consumption is 13 kWh, coverage is 2/3 and reset count is 1. Unknown counter units withhold all numerical counter energy. Eligible fictional P_out=10 kW and loss=1 kW give efficiency approximately 90.9091%; zero output or missing loss inputs leave efficiency null.

## Commands and actual evidence

All analytics/regression commands ran from repository root with Python 3.13. NumPy, pandas, SciPy and scikit-learn were available. No earlier phase suites were rerun.

### PASSED

- Read-only preflight commands above: exit 0.
- `python -m pip install --target "$env:TEMP/h05-validator-dependencies" 'jsonschema==4.26.0'`: exit 0. Isolated validator dependencies installed; pip reported an existing invalid `~ip` distribution warning, which did not prevent installation.
- `python -m unittest ml.tests.test_rul_h05 ml.tests.test_energy_h05 ml.tests.test_h05_session`: final exit 0, **63 tests**, 1.785 seconds. The isolated validator dependency directory was temporarily assigned to PYTHONPATH and the prior value restored afterward. This supplies a test dependency, not a claimed clean installation of the runtime. Generated RUL, energy, analytics and checkpoint outputs were checked with actual Draft 2020-12 JSON Schema validation and format checking against existing H00 schemas; this does not rerun the H00 fixture suite.
- `python -m unittest ml.tests.test_pipeline ml.tests.test_health_index ml.tests.test_maintenance`: final exit 0, **70 tests**, 2.339 seconds. The existing expected incompatible-bundle reset diagnostic appeared. Existing assertions were retained.
- `python -m json.tool ml/rul/fictional_scenario_v1.json`: exit 0.
- `python -m pip wheel --no-deps --no-build-isolation ./ml --wheel-dir "$env:TEMP/h05-runtime-wheel"`: initial H05 export exit 0.
- Final export copied only configured runtime `.py` packages, root `__init__.py`, `pyproject.toml` and fictional scenario JSON to `$env:TEMP/h05-final-export-source`, then ran `python -m pip wheel --no-deps --no-build-isolation $h05ExportRoot --wheel-dir (Join-Path $env:TEMP 'h05-final-runtime-wheel')`: exit 0. Final wheel `transformer_ml_runtime-0.1.0-py3-none-any.whl`, 95,737 bytes, SHA-256 `3fe9b2985cbfe91cfbd3932de697413da4e8f6a2d55f6cfcaac9b82a9fbd4006`. This is an actual packaging checksum, not a fitted-model artifact identity.
- Python `zipfile` inspection of the final wheel: exit 0; H05 modules/types/scenario included, no CSV/notebooks/test modules.
- `git diff --check -- ml/pipeline/orchestrator.py ml/pipeline/session.py ml/pyproject.toml`: exit 0.
- SHA-256 baseline comparison: exit 0; 153 files checked, zero unexpected changes excluding the three declared integration paths. Final branch/HEAD checks matched preflight.
- Python final scope/link check using `git status --short --untracked-files=all`: exit 0; exactly 16 new declared H05 files, three declared integration edits, no unrelated new files, and both added Markdown links resolve.

### FAILED during development, resolved or bypassed honestly

- Initial Python import check including `jsonschema`: failed with `ModuleNotFoundError`. Resolved using the isolated test dependency installation above.
- Attempt to use the previous H01 temporary venv `Scripts/python.exe`: failed because that executable was absent. Tests used the available global Python; no clean-venv install success is claimed.
- First required regression run: 70 tests, one failure in `test_01_stable_response_serialization` because unconditional additive `rul` changed legacy exact top-level keys. Fixed by preserving the legacy shape unless 1.1.0 or explicit synthetic configuration is supplied; the existing test/assertion was not modified. Final 70-test run passed.

### SKIPPED / outside this phase

H00 fixture suite, H01 full regression/release/clean-install suites, H02 SQL suite, H03 protocol/simulator suite and H04 browser suite were not rerun. Numeric conditional insulation-life estimation was not implemented; operational eligibility is the required minimum. No empirical calibration, accuracy comparison, deployment or scale claim was attempted. The wheel check verifies H05 export inclusion; it is not a new clean-environment install/import test.

### BLOCKED / not proven

Real PostgreSQL/broker transactional ingestion, Modbus→MQTT→committed SQL receipt, live backend-to-browser consumption and backend RUL/energy resources remain unverified upstream/H06 gates. H05 pure function and in-memory H01 candidate tests do not prove database rollback/commit or end-to-end delivery. No mock receipt is used as proof of SQL commit.

## H06 integration risks and unmet gates

Person 2 must call these pure functions with bounded persisted event-time records and explicit source/cadence/sign/counter policies, persist RUL through the existing H02 structures, expose the H00 RUL/energy routes and retain H01 prepare/persist/commit/install order. A single runtime owner per asset and compatible checkpoint recovery remain the established H01/H02 assumptions. H05 does not change these backend mechanisms or resolve `anchor=latest|now` queries itself.

Two precise H04 parser incompatibilities were identified in `frontend/src/api/contracts.ts` and left untouched under H05 scope:

1. `rulSchema.superRefine` rejects `SIMULATED_ESTIMATE` when `source_kind=REPLAYED`, although a replay with simulated origin must retain that source kind under H00/H05. H05 validates this result against H00 and never relabels a replay as SIMULATED.
2. `energySchema.superRefine` rejects numerical simulated counter energy when instantaneous-power unit status is UNKNOWN; its counter exception only recognizes `MEASURED_COUNTER`. A synthetic/replayed synthetic kWh counter legitimately uses `energy_method=SIMULATED`, `calculation_method=COUNTER_DIFFERENCE` and may have no instantaneous kW evidence. The H05 counter test proves this result conforms to H00.

H06/frontend integration must resolve those consuming-parser checks without changing provenance or fabricating power units. Until then these valid resources can appear unavailable in the H04 client. Curve API presentation is also unresolved because H00 has no wire curve field; the internal projection/checkpoint curve is ready, but H05 does not invent a resource extension.

Required physical inputs for operational life and measured/verified losses remain absent: verified hotspot/model applicability, liquid/insulation, ageing parameters, defensible life budget, prior exposure, future duty, verified units/coverage, loss parameters, current base and delivered-output boundary. Those omissions deliberately produce nulls. No empirical remaining-life, measured efficiency, measured savings, operational forecast accuracy or end-to-end readiness claim is made.

The deterministic H05 implementation and focused test evidence are available. Outstanding acceptance is integrated SQL/API/browser delivery and the consuming-parser/curve presentation issues above, not additional fictional physical inputs. The exact next dependent phase is **H06 — integrated backend resources and end-to-end demonstration**, per the existing [phase specification](../../phases/05_RUL_AND_ENERGY_ANALYTICS.md). Stop here for manual team review.
