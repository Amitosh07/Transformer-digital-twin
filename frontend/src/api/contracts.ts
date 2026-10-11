import { z } from 'zod';

const num = z.number().finite().nullable();
const text = z.string().nullable();
const time = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/).refine(v => Number.isFinite(Date.parse(v)));
const source = z.enum(['SIMULATED', 'REPLAYED', 'LIVE']);
const priority = z.enum(['NORMAL', 'WATCH', 'PLAN', 'URGENT']);
const strings = z.array(z.string());
export const fieldMetadataSchema = z.object({ unit: text, verification: z.enum(['VERIFIED', 'UNVERIFIED', 'SYNTHETIC_CONFIG']), provenance: z.string(), evidence_reference: text, effective_at: time.nullable() });
export const assetSchema = z.object({
  id: z.string(), name: z.string(), schema_version: z.string(),
  rated_power_kva: num, rated_voltage_hv: num, rated_voltage_lv: num, rated_current_a: num,
  rated_frequency_hz: num.nullish(), vector_group: text.nullish(), impedance_percent: num.nullish(),
  cooling_class: text, oil_type: text, measurement_side: z.enum(['HV','LV','UNKNOWN']).nullish(),
  temperature_rise_limits: z.object({ top_oil_k: num, winding_k: num, hot_spot_k: num, reference: text }).nullish(),
  ct_ratio: z.object({ primary: z.number(), secondary: z.number(), unit: z.literal('A') }).nullish(),
  pt_ratio: z.object({ primary: z.number(), secondary: z.number(), unit: z.literal('V') }).nullish(),
  insulation_type: text.nullish(),
  loss_parameters: z.object({ no_load_kw: num, rated_load_kw: num, reference_temperature_deg_c: num, reference: text }).nullish(),
  configuration_metadata: z.object({ version: z.string(), status: z.enum(['VERIFIED','UNVERIFIED','SYNTHETIC_CONFIG']), field_metadata: z.record(z.string(), fieldMetadataSchema) }).nullish(),
  created_at: time, updated_at: time,
});
export const acquisitionSchema = z.object({
  source_kind: source, source_name: z.string(), origin_kind: z.enum(['SIMULATED','LIVE','UNKNOWN']),
  origin_transformer_id: text, replay_run_id: text, gateway_id: text,
  timestamp_origin: z.enum(['SOURCE_SNAPSHOT','SOURCE_EVENT','GATEWAY_POLL','REPLAY_ASSUMPTION']),
  timezone_status: z.enum(['VERIFIED','DECLARED_UTC','ASSUMED','UNKNOWN']),
  field_units: z.record(z.string(), z.string()), field_verification: z.record(z.string(), z.enum(['VERIFIED','UNVERIFIED','SYNTHETIC'])),
  measurement_side: z.enum(['HV','LV','UNKNOWN']), map_version: text, snapshot_id: text,
  sequence: z.number().int().nonnegative().nullable(), expected_interval_seconds: z.number().positive().nullable(),
});
export const measurements = ['phase_voltage_l1','phase_voltage_l2','phase_voltage_l3','current_l1','current_l2','current_l3','neutral_current','oil_temperature','winding_temperature','ambient_temperature','oil_level','active_power_total','apparent_power_total','reactive_power_total','energy_kwh','power_factor_l1','power_factor_l2','power_factor_l3'] as const;
const numericShape = Object.fromEntries(measurements.map(key => [key, num])) as Record<typeof measurements[number], typeof num>;
export const telemetrySchema = z.object({
  transformer_id: z.string(), timestamp: time, ...numericShape,
  oil_temp_alarm: z.union([z.literal(0), z.literal(1)]).nullable(), oil_temp_trip: z.union([z.literal(0), z.literal(1)]).nullable(),
  magnetic_oil_gauge_alarm: z.union([z.literal(0), z.literal(1)]).nullable(),
  acquisition: acquisitionSchema.nullish(), source_name: text.nullish(), received_at: time.nullish(),
});
const component = z.object({ status: z.enum(['READY','WARMING_UP','INSUFFICIENT_DATA','UNAVAILABLE']), unit: text, coverage_fraction: num, reasons: strings });
export const metadataSchema = z.object({
  thermal_readiness: z.enum(['INITIALIZING','WARMING_UP','READY','GAP_RESET','INSUFFICIENT_FORCING','UNINITIALIZED']).nullish(),
  thermal_model_mode: z.enum(['PUBLIC_EMPIRICAL','VERIFIED_UNIT_EMPIRICAL','STANDARDS_INSPIRED_ELIGIBLE']).nullish(), thermal_temperature_unit: text.nullish(),
  forecast_operational_status: text.nullish(), maintenance_trip_latched: z.boolean().nullish(), maintenance_clear_policy_status: text.nullish(),
  coverage_overall: num.nullish(), health_coverage: num.nullish(),
  apparent_power_utilization: num.nullish(), experimental_fault_risk: num.nullish(),
  extended_reason_codes: strings.optional(), extended_health_reason_codes: strings.optional(), reason_descriptions: z.record(z.string(),z.string()).optional(),
  components: z.object({ thermal: component.nullish(), anomaly: component.nullish(), health: component.nullish(), maintenance: component.nullish(), forecast: component.nullish(), rul: component.nullish() }).nullish(),
  units: z.record(z.string(),z.string()).nullish(),
  coverage: z.object({ start: time.nullable(), end: time.nullable(), covered_seconds: num, expected_seconds: num, fraction: num, gap_count: z.number().int(), missing_fields: strings }).nullish(),
  forecast: z.object({ target_definition: text, horizon_hours: num, release_status: z.enum(['UNRELEASED','INSUFFICIENT_VALIDATION','RELEASED']), operational_eligible: z.boolean(), limitation_codes: strings }).nullish(),
  versions: z.object({ bundle_id: text, configuration_version: text, preprocessing_version: text, artifact_schema_version: text }).nullish(),
  reason_evidence: z.array(z.object({ code: z.string(), trigger: text, value: num, unit: text, threshold: num, reference_source: text, duration_seconds: num })).nullish(),
});
export const rulSchema = z.object({
  rul_status: z.enum(['SIMULATED_ESTIMATE','CONDITIONAL_ESTIMATE','INSUFFICIENT_DATA','NO_CROSSING_WITHIN_HORIZON','END_THRESHOLD_REACHED']),
  rul_method: z.string(), rul_target_definition: z.string(), rul_value: num, rul_unit: z.literal('h'), rul_lower: num, rul_upper: num,
  uncertainty_kind: z.enum(['SCENARIO_RANGE','MODEL_QUANTILES']).nullable(), forecast_horizon_hours: num, future_duty_scenario: text,
  degradation_state: num, end_threshold: num, degradation_unit: text, degradation_rate_per_hour: num, equivalent_ageing_hours: num,
  source_kind: source.nullable(), simulated: z.boolean(), model_version: z.string(), config_version: text,
  required_inputs: strings, assumptions: strings, limitation_codes: strings, coverage_start: time.nullable(), coverage_end: time.nullable(), coverage_fraction: num, timestamp: time,
}).superRefine((value, ctx) => {
  const unavailable = ['INSUFFICIENT_DATA','NO_CROSSING_WITHIN_HORIZON'].includes(value.rul_status);
  if (unavailable && [value.rul_value,value.rul_lower,value.rul_upper].some(v => v !== null)) ctx.addIssue({ code: 'custom', message: 'Unavailable RUL must remain null' });
  if (value.rul_status === 'END_THRESHOLD_REACHED' && value.rul_value !== 0) ctx.addIssue({ code: 'custom', message: 'Endpoint requires zero hours' });
  if (['SIMULATED_ESTIMATE','CONDITIONAL_ESTIMATE'].includes(value.rul_status) && (value.rul_value === null || value.rul_value < 0)) ctx.addIssue({ code: 'custom', message: 'Estimate requires nonnegative hours' });
  if (value.rul_status === 'SIMULATED_ESTIMATE' && (!value.simulated || !['SIMULATED','REPLAYED'].includes(value.source_kind ?? ''))) ctx.addIssue({ code: 'custom', message: 'Synthetic RUL requires simulated provenance' });
});
export const analyticsSchema = z.object({
  transformer_id: z.string().optional(), timestamp: time, inference_status: z.enum(['OK','INSUFFICIENT_DATA']),
  health_index: num, health_components: z.object({ thermal: num, electrical: num, loading: num, oil: num, alarm: num, anomaly: num }).nullable(),
  loading_percent: num, thermal_model_temperature: num, thermal_residual: num, thermal_state: text,
  anomaly_score: num, anomaly_flag: z.boolean().nullable(), fault_risk: num, predicted_fault: text, prediction_confidence: num,
  maintenance_priority: priority.nullish(), maintenance_recommendation: text.nullish(), reason_codes: strings.nullish(), health_reason_codes: strings.nullish(),
  metadata: metadataSchema.nullish(), rul: rulSchema.nullish(), missing_features: strings.optional(), error_detail: text.nullish(), schema_version: z.string(), feature_version: z.string(), model_version: z.string(),
});
// Analytics history intentionally omits health fields in the actual H02 route.
export const analyticsPointSchema = analyticsSchema.omit({ health_index: true, health_components: true });
export const latestSchema = z.object({ transformer: assetSchema, telemetry: telemetrySchema.nullable(), analytics: analyticsSchema.nullable(), open_alerts_count: z.number().int(),
  analytics_availability: z.object({ status: z.enum(['AVAILABLE','INSUFFICIENT_DATA','UNAVAILABLE']), reasons: strings, state_coverage_loss: z.boolean() }).nullish(), schema_version: z.string() });
export const alertSchema = z.object({ id: z.number().int(), transformer_id: z.string(), timestamp: time, severity: z.enum(['INFO','WARNING','CRITICAL']), alert_type: z.string(), trigger: z.string(), evidence: z.record(z.string(),z.unknown()), threshold_or_reason: z.string(), recommended_action: z.string(), status: z.enum(['OPEN','ACKNOWLEDGED','RESOLVED']), last_seen_at: time });
export const maintenanceSchema = z.object({ id: z.number().int(), transformer_id: z.string(), timestamp: time, priority, recommendation: z.string(), reason_codes: strings, status: z.enum(['OPEN','DONE','DISMISSED']) });
export const mqttSchema = z.object({ enabled: z.boolean(), connected: z.boolean(), queue_depth: z.number().int(), committed_count: z.number().int(), conflicted_count: z.number().int(), dropped_count: z.number().int(), last_message_at: time.nullable(), last_error: text });
export const rulResourceSchema = z.object({ transformer_id: z.string(), timestamp: time.nullable(), rul: rulSchema.nullable(), schema_version: z.literal('1.1.0') });
export const energySchema = z.object({
  transformer_id: z.string(), timestamp: time.nullable(), schema_version: z.literal('1.1.0'), energy_status: z.enum(['AVAILABLE','PARTIAL','INSUFFICIENT_DATA','UNAVAILABLE']),
  energy_method: z.enum(['MEASURED_COUNTER','CALCULATED_POWER','SIMULATED','UNAVAILABLE']), calculation_method: z.enum(['COUNTER_DIFFERENCE','TRAPEZOID','NONE']),
  source_kind: source.nullable(), active_power_unit_status: z.enum(['VERIFIED','SYNTHETIC','UNVERIFIED','UNKNOWN']), energy_unit: z.literal('kWh'),
  window_start: time, window_end: time, consumed_kwh: num, covered_consumed_kwh: num, import_kwh: num, export_kwh: num, peak_kw: num,
  loss_kw: num, loss_kwh: num, estimated_savings_kwh: num, efficiency_percent: num, loss_method: text,
  coverage_seconds: z.number().nonnegative(), coverage_fraction: z.number().min(0).max(1), gap_count: z.number().int().nonnegative(), reset_count: z.number().int().nonnegative(),
  missing_intervals: z.array(z.object({ start: time, end: time, reason: z.string() })), peak_time: time.nullable(),
  load_profile: z.array(z.object({ timestamp: time, active_power_total: num })),
  conservation_recommendation: text, conservation_evidence: strings, assumptions: strings, limitation_codes: strings,
  config_version: text, map_version: text, calculation_version: z.string(),
  provenance: z.object({ power_unit: text, counter_unit: text, counter_semantics: text, continuity_evidence: text, measurement_side: z.enum(['HV','LV','UNKNOWN']), maximum_gap_seconds: num, minimum_coverage_fraction: z.number() }),
}).superRefine((value,ctx) => {
  if (value.energy_status !== 'AVAILABLE' && value.consumed_kwh !== null) ctx.addIssue({ code: 'custom', message: 'Incomplete energy cannot claim full-window consumption' });
  if (value.energy_method === 'UNAVAILABLE' && (value.calculation_method !== 'NONE' || value.consumed_kwh !== null || value.covered_consumed_kwh !== null)) ctx.addIssue({ code: 'custom', message: 'Unavailable energy must remain null' });
  if (value.calculation_method !== 'COUNTER_DIFFERENCE' && !['VERIFIED','SYNTHETIC'].includes(value.active_power_unit_status) && [value.consumed_kwh,value.covered_consumed_kwh].some(v=>v!==null)) ctx.addIssue({ code: 'custom', message: 'Power integration requires known units' });
  if (Date.parse(value.window_start) >= Date.parse(value.window_end)) ctx.addIssue({ code: 'custom', message: 'Invalid event-time window' });
});
export const trendSchema = z.object({ start: time, end: time, bucket_seconds: z.number().int().positive(), signals: z.record(z.string(),z.array(z.object({ bucket_start:time, avg:num, min:num, max:num, count:z.number().int().nonnegative() }))), no_data_signals:strings, protection_events:z.array(z.object({ timestamp:time, oil_temp_alarm:num, oil_temp_trip:num, magnetic_oil_gauge_alarm:num })) });
export const pageSchema = <T extends z.ZodType>(item: T) => z.object({ items: z.array(item), total: z.number().int().nonnegative(), limit: z.number().int().positive(), offset: z.number().int().nonnegative() });
export type Asset = z.infer<typeof assetSchema>;
export type Telemetry = z.infer<typeof telemetrySchema>;
export type Analytics = z.infer<typeof analyticsSchema>;
export type AnalyticsPoint = z.infer<typeof analyticsPointSchema>;
export type Latest = z.infer<typeof latestSchema>;
export type RUL = z.infer<typeof rulSchema>;
export type Energy = z.infer<typeof energySchema>;

export const projectionSchema = z.object({ transformer_id:z.string(),timestamp:time.nullable(),projected_curve:z.array(z.object({elapsed_hours:z.number().nonnegative(),degradation:z.number().nonnegative()})),end_threshold:num,degradation_unit:text,forecast_horizon_hours:num,schema_version:z.literal('1.1.0') });
export type Projection = z.infer<typeof projectionSchema>;
