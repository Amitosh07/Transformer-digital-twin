"""Asset configuration and identity metadata for Transformer Digital Twin."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import copy
import hashlib
import json
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class AssetConfig:
    """Asset nameplate and configuration parameters.

    Invariants:
    - loading_percent = 100 * S / S_r (percent)
    - apparent_power_utilization = S / S_r (dimensionless)
    - Both remain None when rated_power_kva is missing or unverified.
    """

    transformer_id: str
    name: str = ""
    rated_power_kva: float | None = None
    rated_voltage_hv: float | None = None
    rated_voltage_lv: float | None = None
    rated_current_a: float | None = None
    cooling_class: str | None = None
    oil_type: str | None = None
    configuration_metadata: Mapping[str, Any] | None = None
    measurement_side: str | None = None
    rated_frequency_hz: float | None = None
    vector_group: str | None = None
    impedance_percent: float | None = None
    temperature_rise_limits: Mapping[str, Any] | None = None
    ct_ratio: Mapping[str, Any] | None = None
    pt_ratio: Mapping[str, Any] | None = None
    insulation_type: str | None = None
    loss_parameters: Mapping[str, Any] | None = None
    # Preserve all additive nameplate fields in checkpoint compatibility identity.
    additional_configuration: Mapping[str, Any] = field(default_factory=dict)

    @property
    def configuration_version(self):
        return (self.configuration_metadata or {}).get('version', 'LEGACY_UNKNOWN')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True,
                              default=str, allow_nan=False).encode()).hexdigest()

    def calculate_loading(self, apparent_power_total_kva: float | None,
                          acquisition=None) -> tuple[float | None, float | None]:
        """Calculate (loading_percent, apparent_power_utilization).

        Returns (None, None) if rated_power_kva is None or S is None.
        Never infers rating from historical data.
        """
        if self.rated_power_kva is None or self.rated_power_kva <= 0:
            return None, None
        if apparent_power_total_kva is None:
            return None, None
        meta = self.configuration_metadata or {}
        rating = meta.get('field_metadata', {}).get('rated_power_kva', {})
        a = acquisition or {}
        synthetic = a.get('source_kind') == 'SIMULATED' or (
            a.get('source_kind') == 'REPLAYED' and a.get('origin_kind') == 'SIMULATED')
        verification = rating.get('verification')
        if rating.get('unit') != 'kVA' or not (
            verification == 'VERIFIED' and bool(rating.get('evidence_reference')) or
            verification == 'SYNTHETIC_CONFIG' and meta.get('status') == 'SYNTHETIC_CONFIG' and synthetic):
            return None, None
        if a.get('field_units', {}).get('apparent_power_total') != 'kVA' or a.get('field_verification', {}).get('apparent_power_total') not in (('VERIFIED', 'SYNTHETIC') if synthetic else ('VERIFIED',)):
            return None, None
        if self.measurement_side not in ('HV', 'LV') or a.get('measurement_side') != self.measurement_side:
            return None, None
        if not math.isfinite(float(apparent_power_total_kva)) or not math.isfinite(float(self.rated_power_kva)):
            return None, None

        utilization = float(apparent_power_total_kva) / float(self.rated_power_kva)
        loading_pct = 100.0 * utilization
        return loading_pct, utilization

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AssetConfig:
        tx_id = str(data.get("id") or data.get("transformer_id") or "TX-UNKNOWN")
        rated_kva = data.get("rated_power_kva") or data.get("ratedPowerKva")
        rated_current = data.get("rated_current_a") or data.get("ratedCurrentA")
        rated_vhv = data.get("rated_voltage_hv") or data.get("voltageHvKv")
        rated_vlv = data.get("rated_voltage_lv") or data.get("voltageLvKv")
        meta = copy.deepcopy(data.get('configuration_metadata'))
        for canonical, alias in (('rated_voltage_hv', 'voltageHvKv'), ('rated_voltage_lv', 'voltageLvKv')):
            evidence = (meta or {}).get('field_metadata', {}).get(alias, {})
            if canonical not in data and alias in data and evidence.get('unit') == 'kV' and evidence.get('verification') in ('VERIFIED', 'SYNTHETIC_CONFIG'):
                if evidence['verification'] == 'VERIFIED' and not evidence.get('evidence_reference'):
                    continue
                value = float(data[alias]) * 1000
                if canonical == 'rated_voltage_hv':
                    rated_vhv = value
                else:
                    rated_vlv = value
                meta['field_metadata'][canonical] = dict(evidence, unit='V')

        return cls(
            transformer_id=tx_id,
            name=str(data.get("name", "")),
            rated_power_kva=float(rated_kva) if rated_kva is not None else None,
            rated_voltage_hv=float(rated_vhv) if rated_vhv is not None else None,
            rated_voltage_lv=float(rated_vlv) if rated_vlv is not None else None,
            rated_current_a=float(rated_current) if rated_current is not None else None,
            cooling_class=data.get("cooling_class") or data.get("coolingClass"),
            oil_type=data.get("oil_type") or data.get("oilType"),
            configuration_metadata=meta,
            measurement_side=data.get('measurement_side'),
            rated_frequency_hz=data.get('rated_frequency_hz'),
            vector_group=data.get('vector_group'), impedance_percent=data.get('impedance_percent'),
            temperature_rise_limits=copy.deepcopy(data.get('temperature_rise_limits')),
            ct_ratio=copy.deepcopy(data.get('ct_ratio')), pt_ratio=copy.deepcopy(data.get('pt_ratio')),
            insulation_type=data.get('insulation_type'), loss_parameters=copy.deepcopy(data.get('loss_parameters')),
            additional_configuration={k: copy.deepcopy(v) for k, v in data.items()
                                      if k not in ('created_at', 'updated_at')},
        )
