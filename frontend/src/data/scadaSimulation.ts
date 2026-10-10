import {
  CanonicalTelemetry,
  DigitalTwinAnalytics,
  ScenarioPreset,
  TransformerAsset,
  HealthComponents,
  MaintenancePriority,
  ThermalState,
} from '../types';

export interface SimulationState {
  asset: TransformerAsset;
  scenario: ScenarioPreset;
  loadPercent: number;
  ambientTemp: number;
  telemetry: CanonicalTelemetry;
  analytics: DigitalTwinAnalytics;
  timeSeries: {
    time: string;
    observedTemp: number;
    modelTemp: number;
    residual: number;
    load: number;
    health: number;
  }[];
}

// Thermodynamic physics model calculation (IEEE Standard Top-Oil Thermal Rise)
export function computeThermalModel(loadRatio: number, ambientC: number): number {
  const ratedTopOilRise = 45.0; // Rated top-oil rise at 100% load (deg C)
  const exponent = 1.6; // IEEE standard oil exponent for natural/forced convection
  const modeledRise = ratedTopOilRise * Math.pow(Math.max(0.1, loadRatio), exponent);
  return Number((ambientC + modeledRise).toFixed(1));
}

export function runTwinSimulation(
  asset: TransformerAsset,
  scenario: ScenarioPreset,
  userLoadPercent: number,
  userAmbientTemp: number
): { telemetry: CanonicalTelemetry; analytics: DigitalTwinAnalytics } {
  const now = new Date().toISOString();
  let load = userLoadPercent;
  let ambient = userAmbientTemp;

  // Apply scenario overrides if not manually forced
  if (scenario === 'OVERLOAD') {
    load = Math.max(load, 138);
  }

  const loadRatio = load / 100;
  const modelTemp = computeThermalModel(loadRatio, ambient);

  let observedTemp = modelTemp + (Math.random() * 1.6 - 0.8);
  let windingTemp = observedTemp + 12.0 * Math.pow(loadRatio, 1.8);
  let oilLevel = 82; // Nominal %
  let oilAlarm = false;
  let oilTrip = false;
  let mogAlarm = false;

  // 3-Phase currents baseline
  const baseCurrent = (asset.ratedCurrentA * loadRatio) / Math.sqrt(3);
  let il1 = baseCurrent * 1.0;
  let il2 = baseCurrent * 0.99;
  let il3 = baseCurrent * 1.01;
  let inut = 3.2; // Nominal balanced neutral current in Amps

  // Voltages baseline
  const baseV = (asset.voltageLvKv * 1000) / Math.sqrt(3);
  let vl1 = baseV * 1.0;
  let vl2 = baseV * 0.998;
  let vl3 = baseV * 1.002;

  // Specific scenario physics divergence
  if (scenario === 'THERMAL_STRESS') {
    // Radiator cooling blocked -> observed temp jumps way above model
    observedTemp = modelTemp + 18.6;
    windingTemp = observedTemp + 21.4;
    if (observedTemp > 90) oilAlarm = true;
    if (observedTemp > 102) oilTrip = true;
  } else if (scenario === 'CURRENT_IMBALANCE') {
    // Unbalanced loading
    il1 = baseCurrent * 1.34;
    il2 = baseCurrent * 0.72;
    il3 = baseCurrent * 0.94;
    inut = baseCurrent * 0.38 + 24.5; // High neutral current
    vl1 = baseV * 0.96;
    vl2 = baseV * 1.03;
  } else if (scenario === 'LOW_OIL') {
    oilLevel = 24.5; // Critical low oil level
    mogAlarm = true; // Magnetic oil gauge alarm trips
    observedTemp += 8.2; // Reduced cooling volume increases temperature
  } else if (scenario === 'OVERLOAD') {
    if (observedTemp > 88) oilAlarm = true;
  }

  // Derived Residual (Key Innovation)
  const thermalResidual = Number((observedTemp - modelTemp).toFixed(1));

  // Determine Thermal State
  let thermalState: ThermalState = 'OPTIMAL';
  if (thermalResidual > 12.0 || observedTemp > 95) thermalState = 'CRITICAL';
  else if (thermalResidual > 5.0 || observedTemp > 80) thermalState = 'ELEVATED';
  else if (observedTemp > 65) thermalState = 'NORMAL';

  // Anomaly Score Calculation (0.0 to 1.0)
  let anomalyScore = 0.05;
  if (scenario === 'THERMAL_STRESS') anomalyScore = 0.89;
  else if (scenario === 'CURRENT_IMBALANCE') anomalyScore = 0.76;
  else if (scenario === 'LOW_OIL') anomalyScore = 0.84;
  else if (scenario === 'OVERLOAD') anomalyScore = 0.68;
  else {
    anomalyScore = Math.min(0.95, Math.max(0.04, (thermalResidual / 20) + (load > 100 ? 0.3 : 0)));
  }
  anomalyScore = Number(anomalyScore.toFixed(2));
  const anomalyFlag = anomalyScore >= 0.60;

  // 6-Pillar Health Components (0 to 100 each)
  const thermalScore = Math.max(10, Math.min(100, Math.round(100 - Math.max(0, thermalResidual * 4.2) - (observedTemp > 85 ? 25 : 0))));
  
  // Current imbalance calculation
  const meanI = (il1 + il2 + il3) / 3;
  const maxDevI = Math.max(Math.abs(il1 - meanI), Math.abs(il2 - meanI), Math.abs(il3 - meanI));
  const currentImbalancePct = Number(((maxDevI / meanI) * 100).toFixed(1));
  const electricalScore = Math.max(15, Math.min(100, Math.round(100 - (currentImbalancePct * 2.2) - (inut > 50 ? 20 : 0))));

  const loadingScore = Math.max(10, Math.min(100, Math.round(load <= 85 ? 100 : 100 - (load - 85) * 1.8)));
  const oilScore = mogAlarm ? 25 : Math.max(20, Math.min(100, Math.round(oilLevel)));
  const alarmScore = (oilTrip ? 0 : (oilAlarm || mogAlarm ? 45 : 100));
  const anomalyPillarScore = Math.round((1 - anomalyScore) * 100);

  const healthComponents: HealthComponents = {
    thermal: thermalScore,
    electrical: electricalScore,
    loading: loadingScore,
    oil: oilScore,
    alarm: alarmScore,
    anomaly: anomalyPillarScore,
  };

  // Weighted Health Index (0 to 100)
  const healthIndex = Number((
    healthComponents.thermal * 0.25 +
    healthComponents.electrical * 0.20 +
    healthComponents.loading * 0.15 +
    healthComponents.oil * 0.15 +
    healthComponents.alarm * 0.15 +
    healthComponents.anomaly * 0.10
  ).toFixed(1));

  // Fault Risk & Prescriptive Recommendation Engine
  let faultRisk = Number((1 - healthIndex / 100).toFixed(2));
  let predictedFault: string | null = null;
  let maintenancePriority: MaintenancePriority = 'NORMAL';
  let recommendation = 'Asset operating within standard design limits. Routine SCADA polling active.';
  const reasonCodes: string[] = [];

  if (healthIndex < 50 || oilTrip || mogAlarm || scenario === 'THERMAL_STRESS' || scenario === 'LOW_OIL') {
    maintenancePriority = 'URGENT';
    if (scenario === 'THERMAL_STRESS') {
      predictedFault = 'THERMAL_RUNAWAY_COOLING_FAILURE';
      recommendation = 'Immediate inspection of radiator cooling fans and forced oil circulation pumps. High risk of insulation dielectric breakdown.';
      reasonCodes.push('RAPID_TEMP_RISE', 'HIGH_OIL_TEMP', 'ANOMALOUS_PATTERN');
    } else if (scenario === 'LOW_OIL' || mogAlarm) {
      predictedFault = 'CONSERVATOR_OIL_LEAKAGE';
      recommendation = 'Deploy maintenance crew for immediate oil sampling, gasket leak remediation, and dielectric oil replenishment.';
      reasonCodes.push('LOW_OIL_LEVEL', 'MOG_ALARM');
    } else {
      predictedFault = 'MULTIVARIATE_CRITICAL_DEGRADATION';
      recommendation = 'Schedule emergency load reduction and physical substation inspection.';
      reasonCodes.push('HIGH_OIL_TEMP', 'OVERLOAD');
    }
  } else if (healthIndex < 70 || scenario === 'OVERLOAD' || scenario === 'CURRENT_IMBALANCE') {
    if (scenario === 'CURRENT_IMBALANCE' || currentImbalancePct > 20) {
      maintenancePriority = 'PLAN';
      predictedFault = 'PHASE_UNBALANCE_NEUTRAL_SURGE';
      recommendation = 'Perform feeder load rebalancing across low-voltage distribution phases to eliminate excessive neutral zero-sequence current.';
      reasonCodes.push('CURRENT_IMBALANCE', 'VOLTAGE_IMBALANCE');
    } else {
      maintenancePriority = 'WATCH';
      predictedFault = 'SUSTAINED_OVERLOAD_STRESS';
      recommendation = 'Shift non-critical feeder loads to adjacent substation to prevent cumulative thermal aging of core paper insulation.';
      reasonCodes.push('OVERLOAD', 'RAPID_TEMP_RISE');
    }
  } else {
    maintenancePriority = 'NORMAL';
    predictedFault = 'NOMINAL_STATE';
  }

  // Canonical Telemetry record
  const telemetry: CanonicalTelemetry = {
    transformer_id: asset.id,
    timestamp: now,
    phase_voltage_l1: Number(vl1.toFixed(1)),
    phase_voltage_l2: Number(vl2.toFixed(1)),
    phase_voltage_l3: Number(vl3.toFixed(1)),
    current_l1: Number(il1.toFixed(1)),
    current_l2: Number(il2.toFixed(1)),
    current_l3: Number(il3.toFixed(1)),
    neutral_current: Number(inut.toFixed(1)),
    oil_temperature: Number(observedTemp.toFixed(1)),
    winding_temperature: Number(windingTemp.toFixed(1)),
    ambient_temperature: Number(ambient.toFixed(1)),
    oil_level: Number(oilLevel.toFixed(1)),
    oil_temp_alarm: oilAlarm,
    oil_temp_trip: oilTrip,
    magnetic_oil_gauge_alarm: mogAlarm,
    active_power_total: Number(((asset.ratedPowerKva * loadRatio * 0.95)).toFixed(1)),
    apparent_power_total: Number(((asset.ratedPowerKva * loadRatio)).toFixed(1)),
    reactive_power_total: Number(((asset.ratedPowerKva * loadRatio * 0.31)).toFixed(1)),
    energy_kwh: 124850.5,
    power_factor_l1: 0.95,
    power_factor_l2: 0.94,
    power_factor_l3: 0.96,
  };

  const analytics: DigitalTwinAnalytics = {
    transformer_id: asset.id,
    timestamp: now,
    loading_percent: Number(load.toFixed(1)),
    thermal_model_temperature: modelTemp,
    thermal_residual: thermalResidual,
    thermal_state: thermalState,
    anomaly_score: anomalyScore,
    anomaly_flag: anomalyFlag,
    health_index: healthIndex,
    health_components: healthComponents,
    fault_risk: faultRisk,
    predicted_fault: predictedFault,
    prediction_confidence: 0.92,
    maintenance_priority: maintenancePriority,
    maintenance_recommendation: recommendation,
    reason_codes: reasonCodes,
    schema_version: '1.0.0',
    feature_version: '1.0.0',
    model_version: '1.0.0',
  };

  return { telemetry, analytics };
}

// Generate 24 historical points leading up to the current state
export function generateTimeSeriesPoints(
  asset: TransformerAsset,
  scenario: ScenarioPreset,
  currentObserved: number,
  currentModel: number
) {
  const points = [];
  const count = 20;

  for (let i = 0; i < count; i++) {
    const tMinusMinutes = (count - 1 - i) * 15;
    const timeLabel = `-${tMinusMinutes}m`;
    const progress = i / (count - 1);

    let loadVal = 65 + Math.sin(i * 0.5) * 8;
    let modelVal = computeThermalModel(loadVal / 100, 30);
    let obsVal = modelVal + (Math.random() * 1.2 - 0.6);
    let healthVal = 92 - Math.random() * 3;

    if (scenario === 'THERMAL_STRESS' && i > 12) {
      // Divergence starts halfway
      const severity = (i - 12) / 8;
      obsVal = modelVal + severity * (currentObserved - currentModel);
      healthVal = 90 - severity * 48;
    } else if (scenario === 'OVERLOAD' && i > 10) {
      loadVal = 70 + ((i - 10) / 10) * 68;
      modelVal = computeThermalModel(loadVal / 100, 32);
      obsVal = modelVal + 2;
      healthVal = 92 - ((i - 10) / 10) * 32;
    } else if (scenario === 'CURRENT_IMBALANCE' && i > 11) {
      healthVal = 91 - ((i - 11) / 9) * 35;
    } else if (scenario === 'LOW_OIL' && i > 13) {
      obsVal = modelVal + ((i - 13) / 7) * 8;
      healthVal = 91 - ((i - 13) / 7) * 55;
    }

    if (i === count - 1) {
      obsVal = currentObserved;
      modelVal = currentModel;
    }

    points.push({
      time: timeLabel,
      observedTemp: Number(obsVal.toFixed(1)),
      modelTemp: Number(modelVal.toFixed(1)),
      residual: Number((obsVal - modelVal).toFixed(1)),
      load: Number(loadVal.toFixed(0)),
      health: Number(Math.max(10, Math.min(100, healthVal)).toFixed(1)),
    });
  }

  return points;
}
