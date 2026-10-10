"""Fictional, explicit scenario parameters. No transformer life constants."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
from .common import event_time, finite

@dataclass(frozen=True)
class Duty:
    hours: float
    rate_per_hour: float
    def __post_init__(self):
        object.__setattr__(self,'hours',finite(self.hours, positive=True))
        object.__setattr__(self,'rate_per_hour',finite(self.rate_per_hour, minimum=0))

@dataclass(frozen=True)
class SyntheticConfig:
    scenario_id: str
    version: str
    start_time: str
    initial_degradation: float | None
    endpoint: float | None
    rate_per_hour: float | None
    horizon_hours: float | None
    maximum_gap_seconds: float
    assume_constant_rate_across_gaps: bool = False
    rate_bounds_per_hour: tuple[float,float] | None = None
    future_duty: tuple[Duty,...] = ()
    def __post_init__(self):
        if not isinstance(self.scenario_id,str) or not self.scenario_id.strip() or not isinstance(self.version,str) or not self.version.strip():
            raise ValueError('scenario identity and version required')
        event_time(self.start_time)
        for key in ('initial_degradation','rate_per_hour'):
            if getattr(self,key) is not None:
                object.__setattr__(self,key,finite(getattr(self,key), minimum=0))
        for key in ('endpoint','horizon_hours'):
            if getattr(self,key) is not None:
                object.__setattr__(self,key,finite(getattr(self,key), positive=True))
        object.__setattr__(self,'maximum_gap_seconds',finite(self.maximum_gap_seconds, positive=True))
        if type(self.assume_constant_rate_across_gaps) is not bool:
            raise ValueError('explicit boolean gap assumption required')
        if self.rate_bounds_per_hour is not None:
            lo,hi = self.rate_bounds_per_hour
            lo=finite(lo, minimum=0); hi=finite(hi, minimum=0)
            object.__setattr__(self,'rate_bounds_per_hour',(lo,hi))
            if self.future_duty or self.rate_per_hour is None or not lo <= self.rate_per_hour <= hi:
                raise ValueError('ordered constant-rate scenario bounds required')
        if len(self.future_duty) > 1024 or any(not isinstance(d,Duty) for d in self.future_duty):
            raise ValueError('bounded future duty required')
    def to_dict(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))
    @classmethod
    def from_dict(cls, value):
        try:
            data = dict(value)
            data['future_duty'] = tuple(Duty(**d) for d in data.get('future_duty',()))
            if data.get('rate_bounds_per_hour') is not None:
                data['rate_bounds_per_hour'] = tuple(data['rate_bounds_per_hour'])
            return cls(**data)
        except (TypeError,KeyError) as exc:
            raise ValueError('malformed synthetic scenario configuration') from exc
    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
