"""Typed H00 resource shape; window summaries are not extra wire members."""
from typing import Literal,TypedDict
from ml.rul.types import SourceKind
class MissingInterval(TypedDict):
    start:str
    end:str
    reason:str
class LoadPoint(TypedDict):
    timestamp:str
    active_power_total:float|None
class EnergyProvenance(TypedDict):
    power_unit:str|None
    counter_unit:str|None
    counter_semantics:str|None
    continuity_evidence:str|None
    measurement_side:Literal['HV','LV','UNKNOWN']
    maximum_gap_seconds:float|None
    minimum_coverage_fraction:float
class EnergyResult(TypedDict):
    transformer_id:str
    timestamp:str|None
    schema_version:Literal['1.1.0']
    energy_status:Literal['AVAILABLE','PARTIAL','INSUFFICIENT_DATA','UNAVAILABLE']
    energy_method:Literal['MEASURED_COUNTER','CALCULATED_POWER','SIMULATED','UNAVAILABLE']
    calculation_method:Literal['COUNTER_DIFFERENCE','TRAPEZOID','NONE']
    source_kind:SourceKind|None
    active_power_unit_status:Literal['VERIFIED','SYNTHETIC','UNVERIFIED','UNKNOWN']
    energy_unit:Literal['kWh']
    window_start:str
    window_end:str
    consumed_kwh:float|None
    covered_consumed_kwh:float|None
    import_kwh:float|None
    export_kwh:float|None
    peak_kw:float|None
    loss_kw:float|None
    loss_kwh:float|None
    estimated_savings_kwh:float|None
    efficiency_percent:float|None
    loss_method:str|None
    coverage_seconds:float
    coverage_fraction:float
    gap_count:int
    reset_count:int
    missing_intervals:list[MissingInterval]
    peak_time:str|None
    load_profile:list[LoadPoint]
    conservation_recommendation:str|None
    conservation_evidence:list[str]
    assumptions:list[str]
    limitation_codes:list[str]
    config_version:str|None
    map_version:str|None
    calculation_version:str
    provenance:EnergyProvenance
