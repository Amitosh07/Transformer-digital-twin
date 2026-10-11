"""H00 wire types and separate checkpoint-only projection points."""
from typing import Literal,TypedDict
SourceKind=Literal['SIMULATED','REPLAYED','LIVE']
class ProjectedPoint(TypedDict):
    elapsed_hours:float
    degradation:float
class RULResult(TypedDict):
    rul_status:Literal['SIMULATED_ESTIMATE','CONDITIONAL_ESTIMATE','INSUFFICIENT_DATA','NO_CROSSING_WITHIN_HORIZON','END_THRESHOLD_REACHED']
    rul_method:str
    rul_target_definition:str
    rul_value:float|None
    rul_unit:Literal['h']
    rul_lower:float|None
    rul_upper:float|None
    uncertainty_kind:Literal['SCENARIO_RANGE','MODEL_QUANTILES']|None
    forecast_horizon_hours:float|None
    future_duty_scenario:str|None
    degradation_state:float|None
    end_threshold:float|None
    degradation_unit:str|None
    degradation_rate_per_hour:float|None
    equivalent_ageing_hours:float|None
    source_kind:SourceKind|None
    simulated:bool
    model_version:str
    config_version:str|None
    required_inputs:list[str]
    assumptions:list[str]
    limitation_codes:list[str]
    coverage_start:str|None
    coverage_end:str|None
    coverage_fraction:float|None
    timestamp:str
