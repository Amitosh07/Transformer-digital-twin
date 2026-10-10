"""
Normal synthetic telemetry generator — simulator_README §5.

Generates physically coherent canonical TransformerRecords where load,
current, power, temperature, ambient conditions, power factor, and oil
condition are coupled (not independently random).

Design notes
─────────────
• A configurable load profile drives currents.
• Power is derived from V × I × PF (not random).
• Oil temperature follows a simplified thermal model: it lags behind
  load with a time constant, offset by ambient.
• Noise is Gaussian and bounded to realistic ranges.
• Missing data is NOT converted to zero (dataschema.md §1.6).
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Optional

import numpy as np

from .schema import TransformerConfig, TransformerRecord


# ---------------------------------------------------------------------------
# Defaults — these are conservative placeholders.
# They must not be presented as verified nameplate data.
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = TransformerConfig(
    transformer_id="TX-001",
    rated_power_kva=500.0,
    rated_voltage_lv=415.0,    # 3-phase LV side (V)
    rated_current_a=695.0,     # ≈ 500 kVA / (√3 × 415 V)
    cooling_class="ONAN",
)

# Typical Indian ambient (source unit — not verified as °C)
_AMBIENT_BASE = 32.0
_AMBIENT_AMPLITUDE = 6.0       # diurnal swing half-amplitude


class SyntheticGenerator:
    """
    Produces a stream of canonical TransformerRecords that model normal
    transformer operation with physically coherent variable coupling.

    Parameters
    ----------
    config : TransformerConfig, optional
        Transformer nameplate / asset metadata.
    seed : int, optional
        RNG seed for reproducibility.
    interval_s : int
        Seconds between generated observations (default 60).
    """

    def __init__(
        self,
        config: Optional[TransformerConfig] = None,
        seed: int = 42,
        interval_s: int = 60,
    ) -> None:
        self.config = config or _DEFAULT_CONFIG
        self.rng = np.random.default_rng(seed)
        self.interval_s = interval_s

        # Internal state
        self._oil_temp: float = _AMBIENT_BASE + 10.0   # initial oil temp
        self._energy_kwh: float = 0.0                    # cumulative energy
        self._step: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        start: _dt.datetime,
        count: int = 1,
    ) -> list[TransformerRecord]:
        """Generate *count* canonical records starting at *start*."""
        records: list[TransformerRecord] = []
        ts = start
        for _ in range(count):
            records.append(self._one_record(ts))
            ts += _dt.timedelta(seconds=self.interval_s)
        return records

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _one_record(self, ts: _dt.datetime) -> TransformerRecord:
        cfg = self.config
        rng = self.rng

        # ── ambient temperature (diurnal cycle) ──────────────────────
        hour_frac = ts.hour + ts.minute / 60.0
        ambient = (
            _AMBIENT_BASE
            + _AMBIENT_AMPLITUDE * math.sin(math.pi * (hour_frac - 6) / 12)
            + rng.normal(0, 0.5)
        )

        # ── load profile (diurnal + noise, 0.2–1.0 pu) ──────────────
        base_load = 0.55 + 0.25 * math.sin(math.pi * (hour_frac - 8) / 12)
        load_pu = float(np.clip(base_load + rng.normal(0, 0.05), 0.15, 1.0))

        rated_i = cfg.rated_current_a or 695.0
        rated_kva = cfg.rated_power_kva or 500.0
        rated_v = cfg.rated_voltage_lv or 415.0

        # ── currents (slight imbalance) ──────────────────────────────
        i_base = load_pu * rated_i
        current_l1 = float(i_base * (1 + rng.normal(0, 0.01)))
        current_l2 = float(i_base * (1 + rng.normal(0, 0.01)))
        current_l3 = float(i_base * (1 + rng.normal(0, 0.01)))
        neutral_current = float(abs(current_l1 - current_l2) * rng.uniform(0.1, 0.3))

        # ── voltages (small variation) ───────────────────────────────
        phase_v = rated_v / math.sqrt(3)   # line-to-neutral
        phase_voltage_l1 = float(phase_v * (1 + rng.normal(0, 0.005)))
        phase_voltage_l2 = float(phase_v * (1 + rng.normal(0, 0.005)))
        phase_voltage_l3 = float(phase_v * (1 + rng.normal(0, 0.005)))

        # ── power factor ─────────────────────────────────────────────
        pf_base = 0.92 + rng.normal(0, 0.02)
        pf_base = float(np.clip(pf_base, 0.80, 1.0))
        power_factor_l1 = float(np.clip(pf_base + rng.normal(0, 0.005), 0.80, 1.0))
        power_factor_l2 = float(np.clip(pf_base + rng.normal(0, 0.005), 0.80, 1.0))
        power_factor_l3 = float(np.clip(pf_base + rng.normal(0, 0.005), 0.80, 1.0))

        # ── power (derived from V, I, PF — not random) ───────────────
        i_avg = (current_l1 + current_l2 + current_l3) / 3.0
        pf_avg = (power_factor_l1 + power_factor_l2 + power_factor_l3) / 3.0
        apparent_power_total = float(math.sqrt(3) * (rated_v) * i_avg / 1000.0)  # kVA
        active_power_total = float(apparent_power_total * pf_avg)                 # kW
        reactive_power_total = float(
            apparent_power_total * math.sqrt(max(0, 1 - pf_avg ** 2))
        )  # kVAr

        # ── cumulative energy ────────────────────────────────────────
        self._energy_kwh += active_power_total * (self.interval_s / 3600.0)
        energy_kwh = round(self._energy_kwh, 2)

        # ── thermal (simplified first-order lag) ─────────────────────
        loading_pct = load_pu * 100.0
        # Steady-state oil temp = ambient + k * (load_pu)^2
        ss_oil = ambient + 25.0 * (load_pu ** 2)
        tau = 0.05  # fast-enough update for per-minute data
        self._oil_temp += tau * (ss_oil - self._oil_temp) + rng.normal(0, 0.2)
        oil_temperature = round(self._oil_temp, 1)

        # Winding temp tracks oil + load-dependent rise
        winding_temperature = round(oil_temperature + 8.0 * load_pu + rng.normal(0, 0.3), 1)

        # ── oil level (stable with minor noise) ──────────────────────
        oil_level = float(round(85.0 + rng.normal(0, 0.3), 1))

        # ── protection (normal = all 0) ──────────────────────────────
        oil_temp_alarm = 0
        oil_temp_trip = 0
        magnetic_oil_gauge_alarm = 0

        self._step += 1

        return TransformerRecord(
            transformer_id=cfg.transformer_id,
            timestamp=ts,
            phase_voltage_l1=round(phase_voltage_l1, 2),
            phase_voltage_l2=round(phase_voltage_l2, 2),
            phase_voltage_l3=round(phase_voltage_l3, 2),
            current_l1=round(current_l1, 2),
            current_l2=round(current_l2, 2),
            current_l3=round(current_l3, 2),
            neutral_current=round(neutral_current, 2),
            oil_temperature=oil_temperature,
            winding_temperature=winding_temperature,
            ambient_temperature=round(ambient, 1),
            oil_level=oil_level,
            oil_temp_alarm=oil_temp_alarm,
            oil_temp_trip=oil_temp_trip,
            magnetic_oil_gauge_alarm=magnetic_oil_gauge_alarm,
            active_power_total=round(active_power_total, 2),
            apparent_power_total=round(apparent_power_total, 2),
            reactive_power_total=round(reactive_power_total, 2),
            energy_kwh=energy_kwh,
            power_factor_l1=round(power_factor_l1, 4),
            power_factor_l2=round(power_factor_l2, 4),
            power_factor_l3=round(power_factor_l3, 4),
        )
