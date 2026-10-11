# RUL and energy strategy

RUL is a confirmed required deliverable. It is currently absent, rather than merely awaiting organizer scope confirmation. Preserve the existing operating HI, anomaly logic and honest forecast gate. Neither anomaly_score nor HI is a time-to-end-of-life target. Findings: [GAP_ANALYSIS.md](GAP_ANALYSIS.md) F05/F07/F09/F10/F11/F13.

## Data feasibility

The organizer workbook is a commissioning/test-comparison sheet with no timestamps, asset lifetime, failure dates, degradation histories, DGA/furan/DP, hot-spot parameters, loss tests or active-power/energy observations. It cannot train or validate empirical RUL. The public historical CSVs mentioned in existing plans are absent from this checkout. Even the plans describe alarm/trip proxies, not run-to-failure lifetime labels. Thus there is no accessible empirical RUL-training basis. Obtain better records before promising a learned RUL predictor.

## RUL tiers and recommended delivery

| Mode | Inputs and prerequisites | Honest output | Current feasibility |
|---|---|---|---|
| Insufficient-data operational mode | Actual source measurements and missing prerequisites | RUL null, explicit reasons and required inputs | Required baseline behavior now |
| Simulated first-passage degradation | Declared synthetic degradation state/history, chosen synthetic end threshold and future duty scenario | Remaining scenario time with simulated provenance, uncertainty scenario range | Best demonstrable mandatory RUL path without real lifetime evidence |
| Thermal-ageing insulation-life budget | Verified hot-spot °C or validated oil→hot-spot model, insulation/liquid/standard applicability, life budget, age/history/consumed equivalent life, future load/ambient | Conditional equivalent ageing and remaining insulation-life budget under declared duty | Not yet eligible; nameplate/source verification needed |
| Empirical condition/degradation model | Repeated DGA/furan/DP/moisture or equivalent physical degradation data, failure threshold model, maintenance confounders and validation | Conditional degradation trajectory and first-passage distribution | No such data accessible |
| Trained survival/RUL predictor | Multiple independent assets with time origins, operating histories, observed end-of-life/failure target and censoring records | Calibrated time-to-defined-event distribution/intervals | Not supported by alarm rows or current workbook |

Recommended hackathon scope: implement the simulated first-passage method and an explicit insufficient-data real-asset result. This creates an actual, reproducible RUL demonstration without inventing empirical accuracy. Also show thermal-ageing eligibility and, only if parameters are verified, a separate conditional insulation-life estimate. Explain to judges what additional asset records promote the demo method to real prognosis. An unavailable card alone is an incomplete demonstration, while a fictional real-asset countdown is misleading.

## Simulated degradation: concrete methodology

Use a synthetic latent degradation state D(t), explicitly separate from operating HI. D=0 represents chosen synthetic starting condition; D_EOL is a declared simulator end-of-life criterion, not a universal transformer threshold. For a simple first demonstration, define nonnegative rate g(t) from a declared synthetic duty/degradation model and integrate using covered elapsed hours:

D_next = D_current + integral(g(t) dt).

Forecast future D under normal/high-load/improved-load scenarios using future load/ambient assumptions; RUL is first time D reaches D_EOL. For a constant chosen rate g>0, RUL_hours=(D_EOL−D_current)/g. For g=0, do not divide or show zero lifetime; return no finite threshold crossing within the scenario horizon. Degradation already beyond threshold yields 0 with end-state flag. Unknown current D, threshold or rate produces null. Source gaps prevent “known consumed life” unless a labelled scenario assumption fills them.

Initialize state from the synthetic scenario itself with versioned seed and synthetic elapsed service history, not HI or oil-temperature percentile. Optional step changes/noise/maintenance interventions belong in the explicit simulator truth model. Do not reset degradation to zero every backend restart. Maintain per-asset state/configuration provenance. Accelerating simulation changes wall playback only, not event-time degradation integration.

Uncertainty: vary declared duty, rate and starting state within documented scenario bounds. Report low/central/high scenario times or quantiles only if a specified stochastic model supports them. A scenario range is not an empirical confidence interval. Provide labelled future degradation chart, threshold, forecast horizon, projected crossing and effect of future load strategy. The curve must not be a decorative countdown disconnected from a state equation.

Validation: analytical constant-rate first passage, variable-rate numerical integration, monotonicity under positive rate, timestep subdivision, duplicate/late sample behavior, missing-history handling, independent asset state, checkpoint/restart, and deterministic seed/replay. Hold out synthetic scenarios to assess simulation behavior, but report that as synthetic validation. No true transformer MAE or remaining-years accuracy without actual targets.

## Conditional thermal ageing

The existing first-order empirical oil-indicator surrogate is not winding hot-spot temperature. Public WTI is binary/status per adapter; it cannot be converted into continuous winding °C. Before ageing calculations, verify sensor semantics/location/unit, same-side currents/ratings, CT/PT ratios, ambient/oil compatibility, cooling/liquid/insulation type, losses and rise tests, hot-spot rise/gradient/exponents/time constants, standard edition and asset applicability. Mineral-oil references cannot silently apply to fictional ester assets.

Represent relative ageing rate as v(theta_H; verified insulation/standard parameters), dimensionless, where theta_H is winding hot-spot temperature in verified °C with any absolute-temperature transformation explicitly in K. Do not apply a Celsius Arrhenius denominator or guess standard reference constants. Equivalent consumed life over a covered interval is:

E_eq_hours = integral(v(theta_H(t)) dt_hours).

If prior consumed equivalent life E_prior and a justified equivalent-life budget L_eq_hours are known, remaining budget B=max(0,L_eq_hours−E_prior−E_eq_hours). For a specified future duty with mean relative ageing rate v_future>0, conditional remaining calendar hours ≈B/v_future; for varying duty, integrate until remaining budget is exhausted. This is an insulation thermal-life-budget estimate; sudden faults, moisture, mechanical stress and other ageing mechanisms can end whole-asset life earlier. Commissioning date alone does not establish consumed equivalent life. Recent thermal stress can support ageing exposure without an absolute RUL.

If L_eq, prior exposure or hot-spot validity is unavailable, return accumulated covered equivalent ageing only if that quantity itself is eligible; RUL stays null. Do not assume every transformer has a generic 20/25/30-year life and subtract age. Explain sensitivity to future ambient/load, hot-spot uncertainty and missing historic exposure. No energy-saving intervention automatically adds measured life years.

Standards evidence: IEC 60076-7:2018 applies to mineral-oil transformers and covers temperatures/loading/thermal ageing (official catalogue https://webstore.iec.ch/en/publication/34351). IEC 60076-2:2011 addresses liquid-immersed cooling and temperature-rise tests (https://webstore.iec.ch/en/publication/599). Catalogue summaries were reviewed; full clauses/constants were not obtained or certified. Indian asset applicability and selected IS edition need verified operator/standards evidence. Do not reuse withdrawn/older standards as universal site limits. These references guide eligibility, not an assertion of compliance.

Research examples reinforce the need for more evidence: IEEE study integrates DGA/insulation/temperature (https://ieeexplore.ieee.org/abstract/document/11271043); lifetime data-fusion/Wiener work uses DGA/DP-derived life index (https://doi.org/10.1109/TPWRD.2023.3305732). Abstract-level evidence reviewed, not full-paper validation or copied thresholds. They do not provide a pretrained model applicable to this asset. A condition model must justify physical measurement-to-degradation-to-endpoint relationships and uncertainty.

## Proposed RUL result contract

Add after schema/backend/ML agreement and version bump; these fields do not currently exist:

| Field | Meaning / allowed behavior |
|---|---|
| rul_status | SIMULATED_ESTIMATE / CONDITIONAL_ESTIMATE / INSUFFICIENT_DATA / NO_CROSSING_WITHIN_HORIZON / END_THRESHOLD_REACHED |
| rul_method, rul_target_definition | Exact degradation or insulation-life endpoint, not generic fault label |
| rul_value, rul_unit | Finite remaining time only when supported; use hours internally, display days/years only with declared conversion |
| rul_lower, rul_upper, uncertainty_kind | Declared scenario bounds/model quantiles, or null; no invented interval confidence |
| forecast_horizon_hours, future_duty_scenario | Horizon and future ambient/load policy assumed |
| degradation_state, end_threshold, equivalent_ageing_hours | Nullable method-specific values with unit/provenance |
| source_kind, simulated, model_version, config_version | Explicit source identity and reproducibility |
| required_inputs, assumptions, limitation_codes | Why insufficient/conditional and what evidence would enable it |
| coverage_start/end, coverage_fraction, timestamp | Covered observation period and event time |

Persist/API/display together. Display “Simulated RUL under scenario …” or “Conditional insulation-life estimate”, not simply “RUL 6 years”. Real-source insufficient result has value/bounds null and specific missing prerequisites. Maintenance may use RUL only under agreed method eligibility; it remains advisory and cannot authorize load/control changes.

## Energy: what available measurements support

Current schema contains P=active_power_total (intended kW), S=apparent_power_total (kVA), Q=reactive_power_total (kVAr), energy_kwh and per-phase PF. The workbook supplies none. Historical source KW/KVA/KVAR/KWH semantics/scale/sign/counter behavior need source verification; names alone do not certify units. Simulator defines values by its synthetic conventions but fault injection currently breaks coupling/energy consistency. Fix F10/F11 before judging energy behavior.

| Quantity | Minimum evidence | Method / unavailable behavior |
|---|---|---|
| Active power trend | Verified meter/source P unit and timestamp | Plot raw P and min/mean/peak with coverage; unverified units qualified |
| Interval/cumulative consumption | Confirmed cumulative kWh counter or covered kW intervals | Counter difference or documented integration; no sum of counter values |
| Demand/load profile | Timestamped P/S plus interval/cadence | Time-weighted daily/peak demand; kVA loading only with matched nameplate |
| Transformer losses | Synchronized input/output active powers or verified no-load/rated-load losses and side/current data | Measured difference or estimated model, separately labelled |
| Efficiency | Boundary-defined input/output power or output plus modelled losses | Nullable without valid denominator/boundary/loss parameters |
| Conservation opportunity | Valid load/PF/loss evidence plus counterfactual plan | Advisory scenario comparison with assumptions, not measured savings |

### Counter-based consumption

Sort by asset/event time; collapse identical retries and quarantine conflicting keys. For confirmed cumulative counter E_i, interval energy is E_i−E_(i−1) within a continuous counter segment. Negative jump is reset/rollover/conflict investigation, not negative consumption or a positive absolute difference. Known rollover may use documented modulus; otherwise start a new segment and exclude ambiguous interval. Never guess register counter width from observed maximum.

Meter cumulative difference can still establish total energy across sparse samples if counter continuity/no reset is independently known; it cannot reconstruct a detailed load profile during the gap. Report that distinction. Clip requested time windows only using known endpoints or explicitly estimated boundary interpolation. Counter start/reset offsets are not energy savings. Directional import/export counters need sign/register semantics; net energy and gross import are different.

### Power integration

For verified instantaneous kW, document bounded previous hold or trapezoidal approximation over valid timestamps. Trapezoidal energy over a covered interval:

DeltaE_kWh = 0.5(P_i+P_(i−1)) × Delta_t_seconds / 3600.

Use only positive, sufficiently covered intervals; exclude long gaps under configured source cadence policy. Interval-average power uses its exact interval support instead. Reject duplicate integration; no missing sample becomes zero, no unlimited hold bridges downtime, and acquisition replay speed must not change event-time energy. Report covered duration, excluded intervals and method. The same asset/window must use one authoritative method; compare counter and integration diagnostically, never add them together.

Acceptance examples (synthetic arithmetic): 10 kW for 2 covered hours →20 kWh; 0→10 kW over 1 h under declared trapezoid →5 kWh; duplicate sample adds zero. Counter 100→110 yields 10 kWh; 110→2 is a new segment, not 108 kWh. Irregular intervals/gaps, unknown units, bidirectional values and counter modulus all need tests. Existing generic SQL average energy counter buckets are not consumption; fetch endpoints or add correct segment-aware aggregates.

### Losses and efficiency

Measured losses = synchronized P_input−P_output at compatible transformer boundaries, with instrument/CT/PT and time uncertainty; small differences can be dominated by measurement error. One-side meter does not measure transformer loss directly. With verified loss tests, a simplified estimated model P_loss=P0+P_load,r×K_I² may be used with temperature/harmonic/connection approximations disclosed. P0 is energized no-load kW, P_load,r rated load loss kW, K_I same-side current ratio. Missing energization status prevents assuming no-load loss disappeared at zero current. For unbalance use appropriately weighted phase I² and connection evidence; no harmonic correction without THD/loss parameters.

Estimated efficiency at output power P_out>0 is 100×P_out/(P_out+P_loss), percent, if those boundaries/parameters are valid. Input-output measurement uses 100×P_out/P_in with valid positive denominator. No-load efficiency is not a useful finite percentage and should be unavailable. DOE distinguishes no-load and load loss components; technical reference https://www.energy.gov/sites/default/files/2022-12/dt-ecs-nopr.pdf (source search evidence, full PDF not inspected). It is an engineering reference, not Indian compliance guidance.

### Conservation recommendations

Use evidence-triggered suggestions: investigate sustained high current/load, compare feasible future load distribution, verify imbalance, review sustained low PF using compatible P/S and phase context, inspect cooling, and identify idle energized loss only with verified P0/configuration. Reactive compensation/load transfer/switching require qualified operator review; recommend assessment, not automatic transformer/protection writes. Improved PF can reduce current/losses for fixed delivered active load but does not itself prove reduced real energy demand.

A load-management demonstration compares same delivered service, common weather/load horizon and declared constraints, then integrates estimated baseline and intervention loss/energy difference. Show absolute kWh and percentage with common denominator and uncertainty, labelled simulated/modelled opportunity. Avoid claiming savings by simply reducing useful energy delivered. Actual savings require before/after or controlled baseline with matched conditions, valid meters, counter reset handling and uncertainty; no fabricated -10%/-20% conservation result.

## Proposed energy result contract

Fields: active_power_unit_status; energy_method (`MEASURED_COUNTER`, `CALCULATED_POWER`, `SIMULATED`, `UNAVAILABLE`); window_start/end; consumed_kwh/import_kwh/export_kwh as appropriate; coverage_seconds/fraction and gap/reset counts; peak_kw/time; load_profile; loss_kw/loss_kwh; efficiency_percent; loss_method; conservation_recommendation/evidence; estimated_savings_kwh only for explicitly defined scenario; assumptions/limitations, asset/config/map/calculation versions and source_kind. Nullable fields remain null when prerequisites fail. Add optional API resources under the existing transformer boundary, without embedding arbitrary raw source names.

## Integration acceptance

Demonstrate one simulated transformer with known rating and explicit source units: observe P/load trend, integrate a covered trace, inject a counter reset/gap, view correctly qualified consumption, then compare two future duty/degradation scenarios. Repeat with missing thermal/nameplate/life inputs: show operational RUL and loss/efficiency unavailable without breaking HI/maintenance. Extend to 25 isolated simulated assets only after these single-asset results agree across storage/API/dashboard.
