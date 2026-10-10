"""Asset identity and nullable nameplate configuration; ratings have no defaults."""

from pydantic import ConfigDict, Field, model_validator
from typing import Literal
from app.schemas.hackathon import (ConfigurationMetadata, TemperatureRiseLimits, CTRatio, PTRatio, LossParameters)

from app.schemas.common import CanonicalModel, FiniteFloat, UtcDatetime


class NameplateFields(CanonicalModel):
    schema_version: Literal['1.0.0','1.1.0'] = '1.0.0'
    rated_frequency_hz: FiniteFloat | None = Field(default=None, gt=0)
    vector_group: str | None = Field(default=None, min_length=1, max_length=128)
    impedance_percent: FiniteFloat | None = Field(default=None, gt=0)
    temperature_rise_limits: TemperatureRiseLimits | None = None
    measurement_side: Literal['HV','LV','UNKNOWN'] | None = None
    ct_ratio: CTRatio | None = None
    pt_ratio: PTRatio | None = None
    insulation_type: str | None = Field(default=None, min_length=1, max_length=128)
    loss_parameters: LossParameters | None = None
    configuration_metadata: ConfigurationMetadata | None = None
    rated_power_kva: FiniteFloat | None = None
    rated_voltage_hv: FiniteFloat | None = None
    rated_voltage_lv: FiniteFloat | None = None
    rated_current_a: FiniteFloat | None = None
    cooling_class: str | None = Field(default=None, max_length=128)
    oil_type: str | None = Field(default=None, max_length=128)

    @model_validator(mode='after')
    def validate_configuration(self):
        meta = self.configuration_metadata
        ratings = ('rated_power_kva','rated_voltage_hv','rated_voltage_lv','rated_current_a')
        if self.schema_version == '1.1.0' or meta is not None:
            for field in ratings:
                value = getattr(self, field)
                if value is not None and value <= 0:
                    raise ValueError('new configuration ratings must be positive')
        if meta is None:
            return self
        units = {'rated_power_kva':'kVA','rated_voltage_hv':'V','rated_voltage_lv':'V',
                 'rated_current_a':'A','rated_frequency_hz':'Hz','impedance_percent':'percent',
                 'ct_ratio.primary':'A','ct_ratio.secondary':'A',
                 'pt_ratio.primary':'V','pt_ratio.secondary':'V'}
        def leaves(data, prefix=''):
            for key, value in data.items():
                if key in ('id','name','schema_version','configuration_metadata','created_at','updated_at'):
                    continue
                path = prefix + key
                if isinstance(value, dict):
                    yield from leaves(value, path + '.')
                elif value is not None:
                    yield path
        for path in leaves(self.model_dump()):
            f = meta.field_metadata.get(path)
            if f is None:
                raise ValueError(f'configuration provenance missing: {path}')
            if meta.status != 'UNVERIFIED' and f.verification != meta.status:
                raise ValueError('aggregate verification disagrees with populated leaf')
            if path in units and f.verification != 'UNVERIFIED' and f.unit != units[path]:
                raise ValueError(f'incompatible configuration unit: {path}')
        return self


class TransformerIn(NameplateFields):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class TransformerOut(TransformerIn):
    model_config = ConfigDict(from_attributes=True)

    created_at: UtcDatetime
    updated_at: UtcDatetime


class TransformerPatch(NameplateFields):
    name: str | None = Field(default=None, min_length=1, max_length=255)
