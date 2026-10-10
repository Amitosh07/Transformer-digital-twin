"""Approximate loss eligibility and dimensionally correct efficiency."""
from __future__ import annotations
from dataclasses import dataclass
from ml.rul.common import finite, synthetic, field_eligible

@dataclass(frozen=True)
class LossModel:
    version: str
    no_load_kw: float
    rated_load_kw: float
    rated_current_a: float
    measurement_side: str
    energized: bool
    output_boundary_reference: str | None
    field_metadata: dict
    def __post_init__(self):
        finite(self.no_load_kw,minimum=0);finite(self.rated_load_kw,minimum=0)
        finite(self.rated_current_a,positive=True)
        if not self.version or self.measurement_side not in ('HV','LV') or type(self.energized) is not bool:
            raise ValueError('invalid loss configuration')
    @classmethod
    def from_asset(cls, asset, *, energized, output_boundary_reference):
        parameters=asset.loss_parameters or {}
        if any(parameters.get(key) is None for key in ('no_load_kw','rated_load_kw')) or asset.rated_current_a is None or asset.measurement_side not in ('HV','LV'):
            return None
        fields=(asset.configuration_metadata or {}).get('field_metadata',{})
        return cls(asset.configuration_version,parameters['no_load_kw'],parameters['rated_load_kw'],
                   asset.rated_current_a,asset.measurement_side,energized,output_boundary_reference,
                   {key:fields.get(key,{}) for key in ('loss_parameters.no_load_kw','loss_parameters.rated_load_kw','rated_current_a')})

def loss_eligible(model, acquisition):
    if model is None or not model.energized or not model.output_boundary_reference:
        return False
    if (acquisition or {}).get('measurement_side')!=model.measurement_side:
        return False
    for key,unit in (('loss_parameters.no_load_kw','kW'),('loss_parameters.rated_load_kw','kW'),('rated_current_a','A')):
        m=model.field_metadata.get(key,{})
        if m.get('unit')!=unit or not (m.get('verification')=='VERIFIED' and m.get('evidence_reference') or m.get('verification')=='SYNTHETIC_CONFIG' and synthetic(acquisition)):
            return False
    return all(field_eligible(acquisition,key,'A') for key in ('current_l1','current_l2','current_l3')) and field_eligible(acquisition,'active_power_total','kW')

def efficiency_percent(delivered_kw,loss_kw):
    if delivered_kw is None or loss_kw is None:
        return None
    delivered_kw=finite(delivered_kw,minimum=0);loss_kw=finite(loss_kw,minimum=0)
    denominator=delivered_kw+loss_kw
    return 100*delivered_kw/denominator if delivered_kw>0 and denominator>0 else None

def interval_loss(model, first, last, seconds):
    """Phase RMS I-squared approximation; linear current between supported endpoints."""
    integrals=[]
    for key in ('current_l1','current_l2','current_l3'):
        a=finite(first[key],minimum=0)/float(model.rated_current_a)
        b=finite(last[key],minimum=0)/float(model.rated_current_a)
        integrals.append((a*a+a*b+b*b)/3)
    mean_loss=float(model.no_load_kw)+float(model.rated_load_kw)*sum(integrals)/3
    return mean_loss*seconds/3600

def synthetic_parameters(model):
    return model is not None and all(m.get('verification')=='SYNTHETIC_CONFIG' for m in model.field_metadata.values()) and len(model.field_metadata)==3
