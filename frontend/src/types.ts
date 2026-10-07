// Canonical Data Schema and Types matching dataschema.md v1.0.0 & mlcontract.md v1.0.0

export type MaintenancePriority = 'NORMAL' | 'WATCH' | 'PLAN' | 'URGENT';

export type ThermalState = 'OPTIMAL' | 'NORMAL' | 'ELEVATED' | 'CRITICAL';

export interface TransformerAsset {
  id: string;
  name: string;
  substation: string;
  ratedPowerKva: number;
  voltageHvKv: number;
  voltageLvKv: number;
  ratedCurrentA: number;
  coolingClass: string;
  oilType: string;
}

export interface CanonicalTelemetry {
  transformer_id: string;
  timestamp: string;
  // Electrical
  phase_voltage_l1: number;
  phase_voltage_l2: number;
  phase_voltage_l3: number;
  current_l1: number;
  current_l2: number;
  current_l3: number;
  neutral_current: number;
  // Thermal
  oil_temperature: number;
  winding_temperature: number;
  ambient_temperature: number;
  // Oil Condition
  oil_level: number;
  // Protection
  oil_temp_alarm: boolean;
  oil_temp_trip: boolean;
  magnetic_oil_gauge_alarm: boolean;
  // Power
  active_power_total: number;
  apparent_power_total: number;
  reactive_power_total: number;
  energy_kwh: number;
  // Power Factor
  power_factor_l1: number;
  power_factor_l2: number;
  power_factor_l3: number;
}

export interface HealthComponents {
  thermal: number;
  electrical: number;
  loading: number;
  oil: number;
  alarm: number;
  anomaly: number;
}

export interface DigitalTwinAnalytics {
  transformer_id: string;
  timestamp: string;
  loading_percent: number;
  thermal_model_temperature: number;
  thermal_residual: number;
  thermal_state: ThermalState;
  anomaly_score: number;
  anomaly_flag: boolean;
  health_index: number;
  health_components: HealthComponents;
  fault_risk: number;
  predicted_fault: string | null;
  prediction_confidence: number;
  maintenance_priority: MaintenancePriority;
  maintenance_recommendation: string;
  reason_codes: string[];
  schema_version: string;
  feature_version: string;
  model_version: string;
}

export type ScenarioPreset = 
  | 'NOMINAL'
  | 'OVERLOAD'
  | 'THERMAL_STRESS'
  | 'CURRENT_IMBALANCE'
  | 'LOW_OIL';

export interface FaultScenarioConfig {
  id: ScenarioPreset;
  title: string;
  badge: string;
  severity: 'OPTIMAL' | 'WARNING' | 'ALERT' | 'CRITICAL';
  description: string;
  expectedOutcome: string;
}
