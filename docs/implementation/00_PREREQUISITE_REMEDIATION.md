# Phase 00 — Prerequisite Remediation

## 1. Phase objective

Repair the existing adapter/features/configuration boundary so later models consume trustworthy, causal, source-provenanced telemetry. Follow AUDIT_PLAN.md; this phase does not redesign ML.

## 2. Scope

Inspect existing data_adapter.py, feature_engineering.py, their tests, dataschema.md, mlcontract.md and repository ML README. Correct production artifact writes, WTI handling, identity/time validation, phase completeness, missingness and feature semantics. Establish asset-configuration and quality metadata boundaries. Regenerate the historical canonical artifact only after tests cannot overwrite it.

## 3. Dependencies

Depends on existing repository and authoritative contracts. Produces corrected canonical/features used by every later phase. Blocks calibration/training. Can independently implement source inspection and regression tests. Must validate before phase 01 and all real-data fitting.

## 4. Inputs

Five supplied source CSVs; existing mapping/aggregation rules; configured synthetic dataset ID; timestamps and source metadata; optional verified asset metadata. The two-row January 2026 canonical attachment is not valid historical training input. Do not derive ratings from the draft measurement/trip worksheet.

## 5. Outputs

- Pure canonical-construction result separated from explicit persistence.
- Regenerated historical canonical file with dataset identity, checksum, row count and time range.
- Aggregate quality report: row_count, missing_count_by_field, duplicate_timestamp_count, timestamp_gap_statistics, out_of_range_count, parse_error_count, source_file, ingestion_timestamp, schema_version.
- Record quality/provenance, conflict/freshness/coverage indicators through an explicitly documented metadata boundary.
- Corrected feature table retaining approved names and explicit feature version.
- Configuration registry containing values or CONFIGURATION REQUIRED, with source/effective date/unit/side.

## 6. Technical specification

### Adapter repair

1. Canonical building must not unconditionally persist to the production path. Tests use temporary locations; no test fixture may replace historical data.
2. Preserve raw files. Collapse identical duplicates. For conflicting measurements, retain conflict counts and aggregation policy. Numeric mean is permitted only as a documented source policy, not universal truth.
3. WTI is raw 0/1, not continuous temperature. Do not average. Until semantics are confirmed, conflicting status duplicates produce unknown/conflict; never create 0.5. Exclude winding_temperature from models.
4. Alarm max means active at least once among duplicate records, not final contact state. Retain conflict/event provenance. Do not infer sub-minute ordering.
5. Counter last-value selection requires trusted sequence/arrival order. Conflicting counters without it are flagged and excluded from interval-energy derivation.
6. Canonical key is (transformer_id,timestamp), not timestamp alone. Validate finite numerics and exact status domain {0,1,missing}.
7. Accept known timezone-aware timestamps; normalize known zones consistently. Keep timezone unknown for naive source data. Do not guess India/UTC from user location.
8. Distinguish required mapped inputs from optional source columns/files. Power.csv contributes no canonical measurement in v1; 27 Power-only timestamps in the audited union require explicit quality-only/exclusion policy for model observations.
9. VL12/VL23/VL31 remain excluded everywhere downstream.

### Feature behavior

Complete existing feature ownership map (no silent renaming):

| Feature names | Definition / unit / readiness |
|---|---|
| current_mean, current_max, current_min | Complete valid phase mean/max/min, A |
| current_imbalance_pct | Existing range/mean formula, %; denominator/three-phase validity required |
| voltage_mean, voltage_imbalance_pct | Complete phase mean V and existing range/mean %, not VUF |
| neutral_current_magnitude | Absolute neutral current, A |
| active_power_demand | active_power_total, kW |
| apparent_power_utilization | S/S_r, dimensionless; null without rating |
| power_factor_mean | Arithmetic mean of valid complete phase PF set, dimensionless; not weighted aggregate PF |
| power_factor_deviation | Existing absolute distance of mean PF from +1; version any approved magnitude-based replacement |
| oil_temperature_level, ambient_temperature_level | Copies of respective source signals with unit status |
| ambient_to_oil_delta | T−A, diagnostic source difference until compatibility verified |
| oil_temperature_rate | Valid adjacent difference per hour |
| temperature_rolling_mean, temperature_rolling_std | Current-inclusive trailing sample mean/SD, oil source unit |
| temperature_slope | Trailing centered least-squares slope, oil source unit/hour |
| thermal_residual | Phase-01 output, null before valid twin assessment |
| oil_level_rolling_mean | Strictly past trailing sample mean, oil source unit |
| oil_level_deviation | Present level minus strictly past mean, oil source unit |
| oil_level_rate | Valid adjacent difference, oil source unit/hour |
| rolling_load_mean, rolling_load_std | Trailing apparent_power_total mean/SD, kVA |
| time_since_last_alarm | Elapsed hours since latest known active oil or MOG alarm, unknown before first observed event |
| time_since_last_trip | Elapsed hours since latest known active trip, unknown before first observed event |

Additional J, frozen-reference oil deviation, time-weighted load/current-squared exposure, readiness/count/age and configured current-loading features require documented feature-version additions. Do not overload existing oil_level_deviation to mean a different reference silently.

Require all three valid phases for three-phase means/spreads used as complete electrical measures. Missing phases never yield a healthy zero imbalance. Validate positive rolling-window duration and unique internal row IDs; preserve caller order without relying on duplicate index labels.

Current-inclusive rolling windows are causal for current inference. Oil reference rolling mean uses [t−W,t), excluding the current observation. Rate/slope/rolling outputs need observation-count and covered-duration readiness. Suppress rates bridging gaps above the 30-minute initial continuity limit. Frozen oil reference and short-term deviation must remain distinguishable; a persistent level loss must not automatically become healthy.

Alarm OR is three-valued: any known 1 → 1; all known 0 → 0; otherwise unknown. Time-since-event remains unknown before the first observed event. Unknown contact intervals break certainty about history.

### Optional source fields

| Fields | Established disposition |
|---|---|
| WL1/WL2/WL3 | Adapter-local power consistency diagnostics; defer model adoption |
| VAL1/VAL2/VAL3 | Defer canonical/model extension pending units/synchrony |
| RVAL1/RVAL2/RVAL3 | Defer; RVAL3 apparent scale discrepancy requires confirmation |
| Avg_PF | Do not use initially; redundant/unweighted meaning uncertain |
| Sum_PF | Do not use as ordinary PF; observed −164.4 to 34.3 |
| FRQ | Defer; useful future frequency/V-f context after approved mapping |
| THDVL1/2/3, THDIL1/2/3 | Defer; no verified limits or harmonic-loss model |
| MDIL1/2/3, MPD, MKVAD | Defer; demand interval/reset semantics unknown |
| KWH_I | Source audit only; investigate negative/large increments |
| KVARH | Defer pending counter/scale semantics |

Do not introduce optional fields into the canonical contract merely because they exist.

## 7. Mathematical/formula specification

### Electrical summaries and phase spread

$$
\bar x=\frac{x_1+x_2+x_3}{3},\qquad
U_{range}=100\frac{x_{max}-x_{min}}{\bar x}
$$

x is three valid phase currents (A) or voltages (V); mean has the same unit and U_range is percent. Denominator must be valid and sufficiently above measurement noise; minimum-current/voltage gate is CONFIGURATION REQUIRED. The existing current_imbalance_pct and voltage_imbalance_pct mean this range/mean metric.

$$
U_{dev}=100\frac{\max_i|x_i-\bar x|}{\bar x}
$$

U_dev is a distinct maximum-deviation metric, percent. Do not substitute under the same feature version. For 10/20/30 A, U_range=100% and U_dev=50%.

$$
VUF=100\frac{|V_2|}{|V_1|}
$$

V_1 and V_2 are positive/negative-sequence voltage phasors, not phase magnitudes. VUF is percent and unavailable from the supplied magnitudes. Do not calculate a fake VUF.

### Heating and loading

$$
J_t=\frac{I_{1,t}^2+I_{2,t}^2+I_{3,t}^2}{3}
$$

I_i are same-side RMS line currents in A; J is A², the approximate aggregate heating driver.

$$
u_S=\frac{S}{S_r},\qquad loading\_percent=100u_S
$$

S and S_r are measured/rated kVA. apparent_power_utilization is u_S, dimensionless; loading_percent is percent. Both are null without verified S_r>0.

$$
I_r=\frac{1000S_r}{\sqrt{3}V_{LL,r}}\quad\text{(three phase)},
\qquad I_r=\frac{1000S_r}{V_r}\quad\text{(single phase)}
$$

Rated voltage is volts, S_r is kVA, I_r is A. Phase count, side, tap and line-to-line versus single-phase voltage must match.

$$
K_{I,eq}=\sqrt{\frac{I_1^2+I_2^2+I_3^2}{3I_r^2}},\qquad
L_{I,max}=100\frac{\max(I_1,I_2,I_3)}{I_r}
$$

K_I,eq is dimensionless aggregate current loading; L_I,max is percent maximum-phase loading. These are distinct from kVA utilization. Equal phase-loss coefficients/connection effects are approximations.

$$
\frac{S}{S_r}\approx\frac{V_{LL}}{V_{LL,r}}\frac{I}{I_r}
$$

Balanced same-side operation only; all ratios dimensionless. Voltage variation explains divergence between current and kVA loading.

### PF and source consistency

$$
PF_{total}=\frac{P}{S},\qquad
d_{PF}=\frac{1}{3}\sum_{i=1}^3(1-|PF_i|)
$$

P is kW and S is kVA; PF and d_PF are dimensionless. Require compatible meter definitions and meaningful nonzero load. d_PF is allowed only after sign interpretation; keep directional sign context. Existing |1−mean(PF)| must not silently acquire this new meaning.

$$
S_{VI}=\frac{\sum_i V_iI_i}{1000}
$$

V_i are compatible phase-to-neutral RMS volts, I_i amps; S_VI is kVA diagnostic, not an automatically substituted meter reading. Audited median S/S_VI≈0.9903 and P/sum(WL)≈1.0033 are whole-dataset descriptive checks, not calibration factors.

### Temporal features

$$
\dot x_t=\frac{x_t-x_{t-1}}{\Delta t_h}
$$

x is oil temperature/level; Δt_h is positive elapsed hours. Rate is source unit/hour. Invalid/long gaps return unavailable.

$$
\bar x_W=\frac{1}{n}\sum_{i\in W}x_i,\qquad
\sigma_W=\sqrt{\frac{\sum_{i\in W}(x_i-\bar x_W)^2}{n-1}}
$$

Sample mean/SD have x's unit; SD requires n≥2. These are sample statistics, not time-weighted exposure. Window is trailing one hour by default.

$$
m_W=\frac{\sum_{i\in W}(u_i-\bar u)(x_i-\bar x)}{\sum_{i\in W}(u_i-\bar u)^2}
$$

u_i is centered time in hours; slope m_W is source unit/hour. Require at least two distinct valid times plus declared coverage; center times to avoid large-number cancellation.

$$
\bar x_{time}=\frac{\sum_i x_i\Delta t_i}{\sum_i\Delta t_i}
$$

Time-weighted mean has x's unit. Use only covered intervals with documented bounded hold semantics; never span unknown long gaps. J exposure uses x=J.

Oil short-term deviation is O_t−mean(O on [t−W,t)), in oil-level source units. Temperature delta is T−A, physical K only if compatible temperature units are verified; otherwise explicitly a source-signal diagnostic. Time since last known active contact is elapsed hours; unknown before observation of an event.

## 8. Parameters and configuration

Keep rolling_window=1 hour and gap limit=30 minutes as configurable heuristics. Sensor resolution/plausibility bounds, low-load denominator gate, source timezone, counter ordering, temperature conversion and contact semantics are CONFIGURATION REQUIRED. Asset rating/cooling/oil/insulation values remain unset until verified. No percentile-based nameplate estimate.

## 9. Processing/algorithm flow

Inspect repository → isolate persistence/test destinations → validate raw schemas → parse time without invented timezone → resolve duplicates with provenance → outer align approved canonical measurements → validate asset/time/domain → calculate quality metadata → sort by asset/time using unique internal rows → generate causal valid features → restore required row ordering → explicitly persist historical artifacts with provenance → run regression and real-data smoke checks.

## 10. Data-quality and missing-data behavior

Keep missing distinct from zero. No blind clipping or interpolation. Non-finite values cannot enter models. Unknown phases/statuses invalidate dependent features. Model-only imputation belongs to a later fitted preprocessing pipeline, not canonical telemetry. Every rejected/withheld quantity has a reason and retained raw evidence.

## 11. Edge cases

Empty input; optional missing source; all-null row; Power-only timestamp; duplicate timestamps across assets; repeated index labels; conflicting WTI; mixed timezone inputs; nonpositive window; infinity; alarm=2; zero current; reverse power; source reset; long gap; partial phases; initial time-since-alarm unknown.

## 12. Leakage/safety constraints

Do not fit reference statistics on the full regenerated dataset. Preserve absolute-time split boundaries from the master plan. No future nearest-neighbor alignment or backward filling. Current-inclusive features are causal, but current event statuses/history must be excluded from initial fault-model inputs. No rating/units from values that merely look plausible.

## 13. Integration requirements

Canonical names stay fixed. Add quality metadata only through an explicit documented contract boundary. Version feature meaning changes. Neutral current magnitude remains |I_N| in A; active_power_demand remains total kW; rolling_load_mean/std remain kVA, not percent. apparent_power_utilization may be filled only by verified configuration; thermal_residual is produced by phase 01, not fabricated here.

## 14. Testing requirements

- Tests cannot alter historical output, including failure paths.
- Raw source hashes unchanged; regenerated artifact carries correct source identity/time range.
- Multi-asset same timestamps accepted; duplicate asset/time rejected/resolved.
- Incomplete phases produce missing spread, not zero.
- WTI conflicts never produce fractional temperature.
- Three-valued alarm OR cases all covered.
- Timezone-aware valid input accepted; unknown timezone not assigned.
- Positive/negative/zero windows, zero denominators, infinity and invalid contacts tested.
- Future-row perturbation leaves earlier features unchanged.
- Long-gap rates suppressed, rolling SD n=1 missing, oil baseline excludes present value.
- Loading arithmetic tested on explicit synthetic ratings, never saved as real asset config.
- Unsorted/repeated-index inputs preserve correct asset/time results.

## 15. Acceptance criteria

All critical source/feature tests pass; production output is safe; historical artifact is traceable; unknown units/ratings remain unknown; schema exclusions preserved; downstream features are causal and validity-gated. Any changed union/count policy is explained against the master reference fingerprints, not silently forced to match.

## 16. Expected behavior

Historical data can enter downstream models with honest quality flags. Missing nameplate yields null loading fields. WTI is not interpreted as winding temperature. Partial phases and gaps do not become normal condition evidence.

## 17. Explicit non-goals

No thermal calibration, anomaly model, HI, fault predictor, maintenance logic, optional-field promotion, standards certification or RUL. Do not replace the architecture or inspect unrelated backend code except necessary boundary compatibility.

## 18. Handoff to subsequent phases

Give phase 01 corrected features (including J), quality/time semantics and source provenance. Give phase 04 immutable split/label source identity. Give phases 02–08 configuration and missingness rules. Report all blocked unit/status/rating confirmations.

## 19. Implementation-agent instructions

Implement this repair scope only. Existing repository structure is authoritative for locations, but not permission to preserve a demonstrated bug. If repository contracts conflict with this approved design, document the discrepancy and make only explicit, versioned phase-relevant changes.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 00_PREREQUISITE_REMEDIATION.md. Inspect the existing repository, schema, ML contract, ML README, adapter, feature implementation and tests before modifying anything. Understand existing behavior. Implement ONLY phase 00, preserving the architecture and approved contracts. Use the documented formulas and meanings exactly; do not invent units, ratings, limits, contact semantics or missing technical values. Do not modify unrelated phases. Isolate all test output from production data, add/update the specified regression tests, run relevant tests and the historical-data validation smoke test. Report changed files, tests executed and results, provenance/count differences, and unresolved CONFIGURATION REQUIRED or NEEDS CONFIRMATION items. Stop after completing this phase.
