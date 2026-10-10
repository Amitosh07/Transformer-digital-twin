"""Explicit source/counter/cadence policies; no inferred meter semantics."""
from __future__ import annotations
from dataclasses import dataclass
from ml.rul.common import finite, event_time

@dataclass(frozen=True)
class EnergyConfig:
    version: str
    method: str
    maximum_gap_seconds: float
    minimum_coverage_fraction: float = 1.0
    power_semantics: str = 'INSTANTANEOUS'
    power_sign: str = 'UNKNOWN'
    counter_semantics: str | None = None
    counter_modulus: float | None = None
    rollover_reference: str | None = None
    continuity_reference: str | None = None
    reset_event_times: tuple[str,...] = ()
    allow_boundary_interpolation: bool = False
    overload_duration_seconds: float | None = None
    maximum_window_seconds: float = 7 * 86400
    maximum_records: int = 250000
    def __post_init__(self):
        if not self.version or self.method not in ('POWER','COUNTER'):
            raise ValueError('explicit version and authoritative energy method required')
        finite(self.maximum_gap_seconds,positive=True)
        finite(self.maximum_window_seconds,positive=True)
        if type(self.maximum_records) is not int or not 2 <= self.maximum_records <= 1000000:
            raise ValueError('safe explicit record count bound required')
        fraction=finite(self.minimum_coverage_fraction,minimum=0)
        if fraction>1:
            raise ValueError('invalid minimum coverage fraction')
        if self.power_semantics not in ('INSTANTANEOUS','INTERVAL_AVERAGE_START','INTERVAL_AVERAGE_END'):
            raise ValueError('unsupported power interval semantics')
        if self.power_sign not in ('UNKNOWN','IMPORT_POSITIVE','IMPORT_ONLY_NONNEGATIVE'):
            raise ValueError('unsupported power sign convention')
        if self.counter_modulus is not None:
            finite(self.counter_modulus,positive=True)
            if not self.rollover_reference:
                raise ValueError('counter modulus requires explicit rollover evidence')
        if type(self.allow_boundary_interpolation) is not bool:
            raise ValueError('explicit boundary interpolation policy required')
        if self.power_semantics!='INSTANTANEOUS' and self.allow_boundary_interpolation:
            raise ValueError('interval-average partial boundaries require separate source evidence')
        for time in self.reset_event_times:
            event_time(time)
        if self.overload_duration_seconds is not None:
            finite(self.overload_duration_seconds,positive=True)
