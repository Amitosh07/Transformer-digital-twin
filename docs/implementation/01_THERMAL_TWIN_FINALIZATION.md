# Phase 01 — Thermal Twin Finalization

## 1. Phase objective

Finalize the established interpretable first-order oil-signal baseline with correct elapsed-time behavior, per-asset persistent state, quality gating and chronological calibration. Do not claim a standards-compliant physical twin from unverified public signals.

## 2. Scope

Replace first-interval-dependent alpha dynamics and active-power-only heating with the specified calibrated current-squared model. Preserve existing thermal output names. Implement readiness, gap resets, signed residuals and absolute-condition separation. Define the future standards-mode prerequisites without inventing parameters or enabling unsupported hot-spot/ageing calculations.

## 3. Dependencies

Depends on phase 00 validated data/features/time/configuration. Produces expected oil signal, signed residual, thermal state/readiness and parameter artifact for 02/04/06/07/08. Blocks residual-based anomaly fitting and fault residual features. Interface/analytical tests may be built on fixtures; real fitting requires phase 00 acceptance. Validate before downstream training.

## 4. Inputs

transformer_id, timestamp, oil_temperature T, ambient_temperature A, three same-side valid RMS currents or phase-00 J, quality/freshness metadata, optional verified asset configuration, persistent prior state and a versioned parameter bundle. Oil observations initialize/evaluate the state; the current oil observation must not be assimilated before scoring its own residual.

## 5. Outputs

thermal_model_temperature (same unit as oil observation); thermal_residual (signed); thermal_state NORMAL/ELEVATED/CRITICAL only when supported, otherwise null; documented readiness/inference status, model mode and uncertainty metadata. Persist previous model temperature, integration timestamp, forcing and its age, segment/reset time, parameter version and readiness. Store fitted parameters, residual evaluation and limitations.

## 6. Technical specification

Modes:

1. **Public empirical mode:** expected oil-indicator behavior in source units. Fit ambient coefficient; never claim verified °C or top-oil location.
2. **Verified-unit empirical mode:** same physical temperature units permit fixed ambient coefficient 1 and nonnegative energized no-load rise.
3. **Future asset-configured standards-inspired mode:** only when rating/loss/rise/cooling/liquid/location data and selected-standard applicability are verified. This phase can define eligibility/interface; do not fill absent values.

Use current-squared forcing rather than signed active power. Reverse power still heats through current. Equal phase-loss coefficients and ignored harmonics/connection effects are explicit approximations. No-load rise applies when energized; zero current is not proof of de-energization.

Use previous-sample hold for instantaneous telemetry. An interval-average source may use its documented interval convention; record it. Never apply a new endpoint load retroactively over a long unknown interval. Retain per-asset state across API calls; a one-row call must not reinitialize from observed oil every time.

Initialize from first valid observed oil plus valid forcing, but withhold residual/normality claims. Absolute verified limits and protection remain independent. Positive residual supports excess-heating evidence; negative residual is model mismatch, not HIGH_OIL_TEMP. A model that correctly predicts high unsafe temperature does not make the condition safe.

State meaning is fixed: NORMAL only when the model is ready and available assessed thermal evidence is within its applicable boundaries; ELEVATED for persistent positive discrepancy or verified warning condition; CRITICAL for verified critical temperature/protection or documented strong corroborated severe evidence. Initialization/insufficiency is null plus status. Statistical reference severity is not by itself a verified physical critical limit. Phase 02 supplies learned severity/persistence when integrated; until those references exist, do not invent residual cutoffs just to populate a state.

## 7. Mathematical/formula specification

### Heating driver

$$
J_t=\frac{I_{1,t}^2+I_{2,t}^2+I_{3,t}^2}{3}
$$

I_i are valid same-side RMS currents in A; J is scalar A². All three phases required. It approximates aggregate load-loss heating.

### Empirical equilibrium and dynamics

$$
T_{\infty,t}=b_0+b_A A_t+b_J J_t
$$

T_infinity is OTI source units; A is ATI source units; b_0 is OTI units, b_A is OTI/ATI units, b_J is OTI units/A². Require b_A≥0, b_J≥0 and τ>0. b_0 is fitted offset in source mode. After compatible physical temperature verification, set b_A=1 and constrain energized b_0≥0.

$$
\frac{d\widehat T}{dt}=\frac{T_\infty-\widehat T}{\tau}
$$

Time and τ are hours; T-hat has T's unit. This is a first-order dynamic surrogate, not complete transformer heat transfer.

For previous forcing u_(t−1)=T_infinity at the prior valid interval boundary:

$$
\widehat T_t=u_{t-1}+(\widehat T_{t-1}-u_{t-1})\exp\left(-\frac{\Delta t}{\tau}\right)
$$

Δt>0 is elapsed hours. Exponent is dimensionless. Exact integration under constant forcing gives monotonic convergence to equilibrium without numerical overshoot.

### Residual and readiness

$$
r_t=T_t-\widehat T_t
$$

r is signed OTI unit or verified °C difference. Suppress at initialization/reset and before readiness; do not assign synthetic zero residual.

$$
\exp(-t_{warm}/\tau)\le\varepsilon,
\qquad t_{warm}\ge-\tau\ln\varepsilon
$$

t_warm is covered valid elapsed time, hours; ε=0.05 is the established heuristic initial-state influence tolerance. Thus t_warm≈3τ. Missing forcing does not count as reliable warm-up history.

### Demonstration of the old alpha defect

$$
\tau=-\frac{\Delta t_{ref}}{\ln(1-\alpha)},\qquad 0<\alpha<1
$$

α is dimensionless response fraction and Δt_ref has time units. With test α=0.5, a 1-minute reference gives τ=1.443 minutes; a 15-minute reference gives τ=21.640 minutes. These are defect demonstrations, not model defaults. Remove runtime dependence on first observed spacing.

### Future standards-inspired oil structure

$$
\Delta\theta_{o,u}=\Delta\theta_{o,r}
\left(\frac{1+R K^2}{1+R}\right)^x
$$

$$
\tau_{eff}\frac{d\theta_o}{dt}=\theta_a+\Delta\theta_{o,u}-\theta_o
$$

K is dimensionless current loading; R=P_load,r/P_0 is rated load-loss/no-load-loss ratio; Δθ_o,r is rated oil rise K; x is dimensionless oil exponent; τ_eff is hours (possibly a declared k_11τ_o formulation); θ_o and θ_a are oil and ambient °C. This provides nonzero energized no-load loss and nonlinear loading response. Parameters and edition-specific applicability are CONFIGURATION REQUIRED. Never borrow illustrative research transformer values for this asset.

## 8. Parameters and configuration

Required fitted/configured values: b_0,b_A,b_J,τ; model mode; source units; interval forcing convention; sensor plausibility policy; residual reference population; bounded hold policy; parameter version. Gap limit initially 30 minutes; warm-up tolerance 0.05; both heuristic. Maximum accepted input age must be explicit and no greater than the documented continuity policy; a more specific hold-age value was not established and requires configuration. No default residual thresholds in physical units were established.

Standards mode additionally requires rated current/side, losses, rated rise, oil exponent, cooling class, liquid/insulation, thermal constants, measured sensor location and selected-standard basis. Hot-spot constants are not supplied.

## 9. Processing/algorithm flow

Validate data/state/config → order one asset's stream → resolve whether interval is covered → initialize/reset if required → integrate previous forcing over valid elapsed time → compare current observation only after prediction → produce residual when ready → assess physical level and signed discrepancy separately → update next forcing and state → return outputs in required order.

Calibration: freeze time partitions → select valid alarm-clear candidate reference segments (not “proven healthy”) → retain suspect spikes for detection testing but exclude known quality anomalies from physical fitting → fit constrained coefficients with robust loss → compare ambient-plus-median-offset, ambient-only dynamic and previous-observation baselines chronologically → accept current contribution only if supported → estimate out-of-sample residual bands → freeze artifact for demo. Optimizer grid/robust-loss tuning were not established; expose/document choices, do not label them standards constants.

For downstream training, produce chronological out-of-fold thermal predictions/residuals. Do not allow whole-training in-sample residuals to inflate fault/anomaly performance claims.

## 10. Data-quality and missing-data behavior

| Case | Behavior |
|---|---|
| Oil missing, forcing valid | Model may continue; residual unavailable |
| Brief missing forcing | Only explicitly configured bounded hold, with estimated-input flag |
| Hold age exceeded | Suspend reliable state claim |
| Gap >30-minute initial policy | New segment, reinitialize when possible, warm-up suppression |
| Suspect oil spike | Preserve and flag; do not automatically assimilate |
| Unknown units | Source-unit mode only |
| Missing rating | Empirical J mode remains possible; no loading-percent invention |
| Missing observation at startup | No initialized model |
| Non-finite state/input | Reject/withhold output and expose reason |

## 11. Edge cases

One-row calls; arbitrary batch boundaries; duplicate timestamp; negative/zero elapsed time; model version change; interleaved assets; unknown energization; very long gap; near-zero fitted current coefficient; unidentifiable τ; large negative residual; observed high temperature with residual near zero; irregular timestamps; stale ambient with fresh current.

## 12. Leakage/safety constraints

No present oil assimilation before residual; no future forcing; no test fitting; no rating inference; no WTI temperature input; no normal classification from initialized zero residual. Do not force physics when current contribution/τ are unsupported. A weaker empirical baseline or unavailable validated model is acceptable with explicit limitation. Thermal CRITICAL cannot be based on absolute residual magnitude alone.

## 13. Integration requirements

Keep existing thermal field names and explicit empirical-input contract clarification from the master. Consumers receive readiness/unit/model-mode metadata through approved versioned additions. Phase 02 owns statistical severity normalization; this module supplies residual and validity. Physical limit assessment and protection can be shared evidence, not duplicate independent votes. State serialization/version compatibility must be defined for phase 07.

## 14. Testing requirements

Analytical constant-forcing update; monotonic heating/cooling; equal result from subdivided intervals under same forcing; fixed τ across different first intervals; chunk/stream equivalence; no cross-asset mixing; future oil perturbation leaves past predictions unchanged; current oil perturbation changes residual but not same-time prediction; startup and reset residual withheld; oil missing with valid forcing; stale forcing suspension; gap restart; infinity rejection; high physical temperature with near-zero residual; negative residual mismatch; reverse-power/current heating consistency. Run chronological calibration smoke evaluation and baseline comparisons.

## 15. Acceptance criteria

All analytical/state tests pass. Learned parameters are constrained, source-provenanced and frozen. Units/mode/readiness are explicit. Validated performance and limitations are recorded; if load contribution is unsupported, no false physical claim is made. Downstream residual training interface supplies out-of-sample evidence. No hot-spot/ageing/RUL output is fabricated.

## 16. Expected behavior

Expected oil responds gradually to changed forcing. Startup is visibly initializing. Missing observation does not automatically stop valid model integration. Long gaps reset confidence. Positive discrepancy is distinguishable from negative mismatch and absolute overheating.

## 17. Explicit non-goals

No full nonlinear multi-state IEC hot-spot implementation; no guessed cooling constants; no winding temperature from WTI; no ageing/percentage life/RUL; no forecast classifier; no redesign of anomaly or health formulas.

## 18. Handoff to subsequent phases

Deliver thermal output schema/readiness, persistent-state contract, parameter/version artifact, held-out and chronological out-of-fold residuals, baseline comparisons, unit limitations and deferred standards configuration list to phases 02, 04, 06–08.

## 19. Implementation-agent instructions

Modify only thermal-related implementation/tests and explicit phase-relevant contract/methodology clarification. Preserve source data and phase-00 behavior. Report parameter identifiability and unsupported capabilities rather than forcing a visually pleasing fit.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 01_THERMAL_TWIN_FINALIZATION.md. Inspect the existing repository, thermal implementation, feature interface, ML contract and tests before editing. Implement ONLY phase 01 with the existing architecture/contracts and the documented equations, units, constraints, persistent state and gap/warm-up rules. Do not invent ratings, sensor units, thermal constants or engineering thresholds. Do not modify unrelated phases. Add/update analytical and state tests, run relevant tests, and perform the chronological calibration/baseline smoke evaluation. Report changed files, tests/results, fitted or unavailable capabilities, and unresolved configuration/confirmation requirements. Stop after this phase.
