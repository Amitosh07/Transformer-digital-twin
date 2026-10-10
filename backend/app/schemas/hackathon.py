"""Typed additive H00 fields; no physical values or algorithm defaults."""
from typing import Literal
from pydantic import Field, StrictBool, field_validator, model_validator, model_serializer
from app.schemas.common import CanonicalModel, FiniteFloat, UtcDatetime
from app.schemas.fields import CANONICAL_TELEMETRY_FIELDS

SourceKind = Literal['SIMULATED', 'REPLAYED', 'LIVE']
Verification = Literal['VERIFIED', 'UNVERIFIED', 'SYNTHETIC']
ConfigVerification = Literal['VERIFIED', 'UNVERIFIED', 'SYNTHETIC_CONFIG']


class Acquisition(CanonicalModel):
    source_kind: SourceKind
    source_name: str = Field(min_length=1, max_length=255)
    origin_kind: Literal['SIMULATED', 'LIVE', 'UNKNOWN']
    origin_transformer_id: str | None = Field(min_length=1, max_length=128)
    replay_run_id: str | None = Field(min_length=1)
    gateway_id: str | None = Field(min_length=1)
    timestamp_origin: Literal['SOURCE_SNAPSHOT', 'SOURCE_EVENT', 'GATEWAY_POLL', 'REPLAY_ASSUMPTION']
    timezone_status: Literal['VERIFIED', 'DECLARED_UTC', 'ASSUMED', 'UNKNOWN']
    field_units: dict[str, str]
    field_verification: dict[str, Verification]
    measurement_side: Literal['HV', 'LV', 'UNKNOWN']
    map_version: str | None = Field(min_length=1)
    snapshot_id: str | None = Field(pattern='^[0-9a-f]{64}$')
    sequence: int | None = Field(strict=True, ge=0)
    expected_interval_seconds: FiniteFloat | None = Field(gt=0)

    @field_validator('source_name', 'origin_transformer_id', 'replay_run_id', 'gateway_id', 'map_version')
    @classmethod
    def source_identity(cls, value):
        if value is not None and (value != value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError('source identity contains whitespace or control characters')
        return value

    @model_validator(mode='after')
    def provenance(self):
        fields = set(CANONICAL_TELEMETRY_FIELDS) - {'transformer_id', 'timestamp'}
        if set(self.field_units) != fields or set(self.field_verification) != fields:
            raise ValueError('unit/verification maps require all 21 canonical measurements')
        synthetic = self.source_kind == 'SIMULATED' or (self.source_kind == 'REPLAYED' and self.origin_kind == 'SIMULATED')
        if self.source_kind == 'REPLAYED' and (not self.origin_transformer_id or not self.replay_run_id):
            raise ValueError('replay requires origin asset and run identity')
        if self.timezone_status == 'UNKNOWN':
            raise ValueError('unknown timezone must be staged')
        if self.timezone_status == 'DECLARED_UTC' and not synthetic:
            raise ValueError('declared UTC requires synthetic origin')
        if self.timezone_status == 'ASSUMED' and (self.source_kind != 'REPLAYED' or self.timestamp_origin != 'REPLAY_ASSUMPTION'):
            raise ValueError('timezone assumption requires deliberate replay')
        units = {**dict.fromkeys(['phase_voltage_l1','phase_voltage_l2','phase_voltage_l3'], {'V'}),
                 **dict.fromkeys(['current_l1','current_l2','current_l3','neutral_current'], {'A'}),
                 **dict.fromkeys(['oil_temp_alarm','oil_temp_trip','magnetic_oil_gauge_alarm'], {'STATUS'}),
                 'oil_temperature': {'DEG_C','SOURCE_UNIT'}, 'ambient_temperature': {'DEG_C','SOURCE_UNIT'},
                 'winding_temperature': {'STATUS','SOURCE_UNIT'}, 'oil_level': {'percent','SOURCE_UNIT'},
                 'active_power_total': {'kW'}, 'apparent_power_total': {'kVA'}, 'reactive_power_total': {'kVAr'},
                 'energy_kwh': {'kWh'}, **dict.fromkeys(['power_factor_l1','power_factor_l2','power_factor_l3'], {'1','dimensionless'})}
        for name, unit in self.field_units.items():
            status = self.field_verification[name]
            if not unit or (unit == 'UNKNOWN' and status != 'UNVERIFIED'):
                raise ValueError('unknown units cannot be verified')
            if status == 'SYNTHETIC' and not synthetic:
                raise ValueError('synthetic verification requires simulated origin')
            if status != 'UNVERIFIED' and unit not in units[name]:
                raise ValueError(f'incompatible unit for {name}')
        return self


class ConfigurationField(CanonicalModel):
    unit: str | None
    verification: ConfigVerification
    provenance: str = Field(min_length=1)
    evidence_reference: str | None
    effective_at: UtcDatetime | None

    @model_validator(mode='after')
    def evidence(self):
        if self.verification == 'VERIFIED' and not self.evidence_reference:
            raise ValueError('verified configuration requires evidence')
        return self


class ConfigurationMetadata(CanonicalModel):
    version: str = Field(min_length=1)
    status: ConfigVerification
    field_metadata: dict[str, ConfigurationField]


class TemperatureRiseLimits(CanonicalModel):
    top_oil_k: FiniteFloat | None = Field(gt=0)
    winding_k: FiniteFloat | None = Field(gt=0)
    hot_spot_k: FiniteFloat | None = Field(gt=0)
    reference: str | None


class CTRatio(CanonicalModel):
    primary: FiniteFloat = Field(gt=0)
    secondary: FiniteFloat = Field(gt=0)
    unit: Literal['A']


class PTRatio(CTRatio):
    unit: Literal['V']


class LossParameters(CanonicalModel):
    no_load_kw: FiniteFloat | None = Field(ge=0)
    rated_load_kw: FiniteFloat | None = Field(ge=0)
    reference_temperature_deg_c: FiniteFloat | None
    reference: str | None


class ComponentReadiness(CanonicalModel):
    status: Literal['READY', 'WARMING_UP', 'INSUFFICIENT_DATA', 'UNAVAILABLE']
    unit: str | None
    coverage_fraction: FiniteFloat | None = Field(ge=0, le=1)
    reasons: list[str]


class Components(CanonicalModel):
    thermal: ComponentReadiness | None = None
    anomaly: ComponentReadiness | None = None
    health: ComponentReadiness | None = None
    maintenance: ComponentReadiness | None = None
    forecast: ComponentReadiness | None = None
    rul: ComponentReadiness | None = None

    @model_serializer(mode='wrap')
    def omit_absent(self, handler):
        return {k:v for k,v in handler(self).items() if v is not None}


class Coverage(CanonicalModel):
    start: UtcDatetime | None
    end: UtcDatetime | None
    covered_seconds: FiniteFloat | None = Field(ge=0)
    expected_seconds: FiniteFloat | None = Field(ge=0)
    fraction: FiniteFloat | None = Field(ge=0, le=1)
    gap_count: int = Field(strict=True, ge=0)
    missing_fields: list[str]


class ForecastMetadata(CanonicalModel):
    target_definition: str | None
    horizon_hours: FiniteFloat | None = Field(gt=0)
    release_status: Literal['UNRELEASED', 'INSUFFICIENT_VALIDATION', 'RELEASED']
    operational_eligible: StrictBool
    limitation_codes: list[str]


class MetadataVersions(CanonicalModel):
    bundle_id: str | None
    configuration_version: str | None
    preprocessing_version: str | None
    artifact_schema_version: str | None


class ReasonEvidence(CanonicalModel):
    code: str = Field(min_length=1)
    trigger: str | None
    value: FiniteFloat | None
    unit: str | None
    threshold: FiniteFloat | None
    reference_source: str | None
    duration_seconds: FiniteFloat | None = Field(ge=0)


class AnalyticsMetadata(CanonicalModel):
    thermal_readiness: Literal['INITIALIZING','WARMING_UP','READY','GAP_RESET','INSUFFICIENT_FORCING','UNINITIALIZED'] | None = None
    thermal_model_mode: Literal['PUBLIC_EMPIRICAL','VERIFIED_UNIT_EMPIRICAL','STANDARDS_INSPIRED_ELIGIBLE'] | None = None
    thermal_temperature_unit: str | None = None
    apparent_power_utilization: FiniteFloat | None = None
    forecast_operational_status: str | None = None
    experimental_fault_risk: FiniteFloat | None = Field(default=None, ge=0, le=1)
    maintenance_trip_latched: StrictBool | None = None
    maintenance_clear_policy_status: str | None = None
    coverage_overall: FiniteFloat | None = Field(default=None, ge=0, le=1)
    health_coverage: FiniteFloat | None = Field(default=None, ge=0, le=1)
    extended_reason_codes: list[str] = Field(default_factory=list)
    extended_health_reason_codes: list[str] = Field(default_factory=list)
    reason_descriptions: dict[str, str] = Field(default_factory=dict)
    components: Components | None = None
    units: dict[str, str] | None = None
    coverage: Coverage | None = None
    forecast: ForecastMetadata | None = None
    versions: MetadataVersions | None = None
    reason_evidence: list[ReasonEvidence] | None = None

    @model_serializer(mode='wrap')
    def omit_absent_objects(self, handler):
        result = handler(self)
        for key in ('components','units','coverage','forecast','versions','reason_evidence'):
            if result.get(key) is None:
                result.pop(key, None)
        return result


class RULResult(CanonicalModel):
    rul_status: Literal['SIMULATED_ESTIMATE','CONDITIONAL_ESTIMATE','INSUFFICIENT_DATA','NO_CROSSING_WITHIN_HORIZON','END_THRESHOLD_REACHED']
    rul_method: str = Field(min_length=1)
    rul_target_definition: str = Field(min_length=1)
    rul_value: FiniteFloat | None = Field(ge=0)
    rul_unit: Literal['h']
    rul_lower: FiniteFloat | None = Field(ge=0)
    rul_upper: FiniteFloat | None = Field(ge=0)
    uncertainty_kind: Literal['SCENARIO_RANGE','MODEL_QUANTILES'] | None
    forecast_horizon_hours: FiniteFloat | None = Field(gt=0)
    future_duty_scenario: str | None
    degradation_state: FiniteFloat | None = Field(ge=0)
    end_threshold: FiniteFloat | None = Field(gt=0)
    degradation_unit: str | None
    degradation_rate_per_hour: FiniteFloat | None = Field(ge=0)
    equivalent_ageing_hours: FiniteFloat | None = Field(ge=0)
    source_kind: SourceKind | None
    simulated: StrictBool
    model_version: str = Field(min_length=1)
    config_version: str | None
    required_inputs: list[str]
    assumptions: list[str]
    limitation_codes: list[str]
    coverage_start: UtcDatetime | None
    coverage_end: UtcDatetime | None
    coverage_fraction: FiniteFloat | None = Field(ge=0, le=1)
    timestamp: UtcDatetime

    @model_validator(mode='after')
    def eligibility(self):
        if (self.required_inputs or self.rul_status in ('INSUFFICIENT_DATA','NO_CROSSING_WITHIN_HORIZON')) and any(v is not None for v in (self.rul_value,self.rul_lower,self.rul_upper)):
            raise ValueError('unavailable RUL must remain null')
        if self.rul_status == 'SIMULATED_ESTIMATE' and not self.simulated:
            raise ValueError('synthetic RUL requires scenario label')
        if self.simulated and self.source_kind not in ('SIMULATED','REPLAYED'):
            raise ValueError('synthetic RUL cannot represent a live asset life')
        return self


class AnalyticsAvailability(CanonicalModel):
    status: Literal['AVAILABLE','INSUFFICIENT_DATA','UNAVAILABLE']
    reasons: list[str]
    state_coverage_loss: StrictBool
