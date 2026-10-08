"""Asset configuration and identity metadata for Transformer Digital Twin."""

from __future__ import annotations

from dataclasses import dataclass
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

    def calculate_loading(self, apparent_power_total_kva: float | None) -> tuple[float | None, float | None]:
        """Calculate (loading_percent, apparent_power_utilization).

        Returns (None, None) if rated_power_kva is None or S is None.
        Never infers rating from historical data.
        """
        if self.rated_power_kva is None or self.rated_power_kva <= 0:
            return None, None
        if apparent_power_total_kva is None:
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

        return cls(
            transformer_id=tx_id,
            name=str(data.get("name", "")),
            rated_power_kva=float(rated_kva) if rated_kva is not None else None,
            rated_voltage_hv=float(rated_vhv) if rated_vhv is not None else None,
            rated_voltage_lv=float(rated_vlv) if rated_vlv is not None else None,
            rated_current_a=float(rated_current) if rated_current is not None else None,
            cooling_class=data.get("cooling_class") or data.get("coolingClass"),
            oil_type=data.get("oil_type") or data.get("oilType"),
        )
