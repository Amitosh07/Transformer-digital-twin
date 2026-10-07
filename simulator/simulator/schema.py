"""
Canonical TransformerRecord schema — strict implementation of dataschema.md v1.0.0.

Every generated record uses ONLY the canonical field names defined in the shared
data contract.  No simulator-specific aliases are allowed at module boundaries.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Canonical record
# ---------------------------------------------------------------------------

class TransformerRecord(BaseModel):
    """
    One observation for a single transformer at a single timestamp.

    Field names, types, and semantics match dataschema.md §3–§10 exactly.
    """

    # ── identity ──────────────────────────────────────────────────────────
    transformer_id: str = Field(
        ..., description="Stable asset identifier (system / simulator / utility)."
    )
    timestamp: _dt.datetime = Field(
        ..., description="ISO-8601, timezone-aware when known."
    )

    # ── electrical ────────────────────────────────────────────────────────
    phase_voltage_l1: Optional[float] = Field(None, description="Phase line 1 voltage (V).")
    phase_voltage_l2: Optional[float] = Field(None, description="Phase line 2 voltage (V).")
    phase_voltage_l3: Optional[float] = Field(None, description="Phase line 3 voltage (V).")
    current_l1: Optional[float] = Field(None, description="Line current 1 (A).")
    current_l2: Optional[float] = Field(None, description="Line current 2 (A).")
    current_l3: Optional[float] = Field(None, description="Line current 3 (A).")
    neutral_current: Optional[float] = Field(None, description="Neutral current (A).")

    # ── thermal ───────────────────────────────────────────────────────────
    oil_temperature: Optional[float] = Field(None, description="Oil temperature (source unit).")
    winding_temperature: Optional[float] = Field(None, description="Winding temperature (source unit / status).")
    ambient_temperature: Optional[float] = Field(None, description="Ambient temperature (source unit).")

    # ── oil condition ─────────────────────────────────────────────────────
    oil_level: Optional[float] = Field(None, description="Oil level (source-defined unit).")

    # ── protection / alarm states ─────────────────────────────────────────
    oil_temp_alarm: Optional[int] = Field(None, ge=0, le=1, description="Oil-temperature alarm (0/1).")
    oil_temp_trip: Optional[int] = Field(None, ge=0, le=1, description="Oil-temperature trip (0/1).")
    magnetic_oil_gauge_alarm: Optional[int] = Field(None, ge=0, le=1, description="Magnetic oil gauge alarm (0/1).")

    # ── power ─────────────────────────────────────────────────────────────
    active_power_total: Optional[float] = Field(None, description="Total active power (kW).")
    apparent_power_total: Optional[float] = Field(None, description="Total apparent power (kVA).")
    reactive_power_total: Optional[float] = Field(None, description="Total reactive power (kVAr).")
    energy_kwh: Optional[float] = Field(None, description="Cumulative energy (kWh).")

    # ── power factor ──────────────────────────────────────────────────────
    power_factor_l1: Optional[float] = Field(None, description="Power factor phase L1 (dimensionless).")
    power_factor_l2: Optional[float] = Field(None, description="Power factor phase L2 (dimensionless).")
    power_factor_l3: Optional[float] = Field(None, description="Power factor phase L3 (dimensionless).")

    class Config:
        json_schema_extra = {
            "schema_version": SCHEMA_VERSION,
        }


# ---------------------------------------------------------------------------
# Asset / nameplate configuration (dataschema.md §11)
# ---------------------------------------------------------------------------

class TransformerConfig(BaseModel):
    """
    Asset metadata / nameplate.  Required for the twin but not guaranteed
    in the public dataset.  Values here are configurable defaults — they
    must NOT be presented as verified nameplate data unless confirmed.
    """

    transformer_id: str = "TX-001"
    rated_power_kva: Optional[float] = None
    rated_voltage_hv: Optional[float] = None
    rated_voltage_lv: Optional[float] = None
    rated_current_a: Optional[float] = None
    cooling_class: Optional[str] = None
    oil_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Source mapping (dataschema.md §19) — Kaggle CSV column ↔ canonical
# ---------------------------------------------------------------------------

# Used by the replay adapter when reading baseline CSV data.
SOURCE_TO_CANONICAL: dict[str, str] = {
    "DeviceTimeStamp": "timestamp",
    "VL1": "phase_voltage_l1",
    "VL2": "phase_voltage_l2",
    "VL3": "phase_voltage_l3",
    "IL1": "current_l1",
    "IL2": "current_l2",
    "IL3": "current_l3",
    "INUT": "neutral_current",
    "OTI": "oil_temperature",
    "WTI": "winding_temperature",
    "ATI": "ambient_temperature",
    "OLI": "oil_level",
    "OTI_A": "oil_temp_alarm",
    "OTI_T": "oil_temp_trip",
    "MOG_A": "magnetic_oil_gauge_alarm",
    "PFL1": "power_factor_l1",
    "PFL2": "power_factor_l2",
    "PFL3": "power_factor_l3",
}

# dataschema.md §5 — explicitly excluded fields
EXCLUDED_SOURCE_FIELDS: set[str] = {"VL12", "VL23", "VL31"}


# ---------------------------------------------------------------------------
# Scenario metadata (simulator_README §8)
# ---------------------------------------------------------------------------

class ScenarioMetadata(BaseModel):
    """Metadata attached to every fault-injection scenario."""

    scenario_id: str
    description: str = ""
    start_time: Optional[_dt.datetime] = None
    end_time: Optional[_dt.datetime] = None
    severity: str = Field(
        ..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$",
        description="Scenario severity."
    )
    injected_variables: list[str] = Field(
        default_factory=list,
        description="Canonical field names modified by the injection."
    )
    expected_response: list[str] = Field(
        default_factory=list,
        description="Human-readable expected downstream responses."
    )
