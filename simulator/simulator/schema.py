"""
Canonical TransformerRecord schema — strict implementation of dataschema.md v1.0.0.

Every generated record uses ONLY the canonical field names defined in the shared
data contract.  No simulator-specific aliases are allowed at module boundaries.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from ml.pipeline.identity import FIELDS, PROTECTION, utc, payload_hash

SCHEMA_VERSION = "1.1.0"

# ---------------------------------------------------------------------------
# Canonical record
# ---------------------------------------------------------------------------

class TransformerRecord(BaseModel):
    """
    One observation for a single transformer at a single timestamp.

    Field names, types, and semantics match dataschema.md §3–§10 exactly.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: str = Field("1.0.0", pattern=r"^1\.[01]\.0$")
    source_name: Optional[str] = None
    scenario_id: Optional[str] = None
    acquisition: Optional[dict] = None

    @field_validator(*(key for key in FIELDS if key not in PROTECTION), mode="before")
    @classmethod
    def numeric(cls, value):
        from decimal import Decimal
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float, Decimal))):
            raise ValueError("numeric measurements require JSON numbers")
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def aware_time(cls, value):
        utc(value)
        return value

    @field_validator(*PROTECTION, mode="before")
    @classmethod
    def contact(cls, value):
        if value is not None and (type(value) not in (bool, int) or value not in (0, 1)):
            raise ValueError("protection must be boolean or integer 0/1")
        return None if value is None else int(value)

    @field_validator("transformer_id")
    @classmethod
    def asset_id(cls, value):
        if not value or value != value.strip() or len(value) > 128 or any(c in value for c in "/+#") or any(ord(c) < 32 for c in value):
            raise ValueError("invalid asset/topic identity")
        return value

    @field_validator("power_factor_l1", "power_factor_l2", "power_factor_l3")
    @classmethod
    def pf(cls, value):
        if value is not None and not -1 <= value <= 1:
            raise ValueError("power factor outside [-1, 1]")
        return value

    @model_validator(mode="after")
    def provenance(self):
        if self.acquisition is not None:
            acq = Acquisition.model_validate(self.acquisition)
            if self.source_name is not None and self.source_name != acq.source_name:
                raise ValueError("flat and acquisition source names disagree")
            if acq.source_kind == "REPLAYED" and acq.origin_transformer_id == self.transformer_id:
                raise ValueError("replay destination must differ from origin")
        return self

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
    measurement_side: str = "LV"
    configuration_status: str = "SYNTHETIC_CONFIG"
    configuration_version: str = "fictional-demo-v1"

    @field_validator("rated_power_kva", "rated_voltage_hv", "rated_voltage_lv", "rated_current_a")
    @classmethod
    def positive(cls, value):
        import math
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("fictional ratings must be finite and positive")
        return value

    @model_validator(mode="after")
    def fictional(self):
        if self.configuration_status != "SYNTHETIC_CONFIG" or self.measurement_side != "LV":
            raise ValueError("generator accepts explicitly fictional LV configurations only")
        return self


class Acquisition(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source_kind: str
    source_name: str = Field(min_length=1)
    origin_kind: str
    origin_transformer_id: Optional[str]
    replay_run_id: Optional[str]
    gateway_id: Optional[str]
    timestamp_origin: str
    timezone_status: str
    field_units: dict[str, str]
    field_verification: dict[str, str]
    measurement_side: str
    map_version: Optional[str]
    snapshot_id: Optional[str] = Field(pattern=r"^[0-9a-f]{64}$")
    sequence: Optional[int] = Field(ge=0, strict=True)
    expected_interval_seconds: Optional[float] = Field(gt=0)

    @field_validator("source_name", "origin_transformer_id", "replay_run_id", "gateway_id", "map_version")
    @classmethod
    def source_identity(cls, value):
        if value is not None and (not value or value != value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("invalid source identity")
        return value

    @model_validator(mode="after")
    def semantics(self):
        if self.source_kind not in ("SIMULATED", "REPLAYED", "LIVE") or self.origin_kind not in ("SIMULATED", "LIVE", "UNKNOWN"):
            raise ValueError("invalid source kind")
        if self.timestamp_origin not in ("SOURCE_SNAPSHOT", "SOURCE_EVENT", "GATEWAY_POLL", "REPLAY_ASSUMPTION"):
            raise ValueError("invalid timestamp origin")
        if self.timezone_status not in ("VERIFIED", "DECLARED_UTC", "ASSUMED"):
            raise ValueError("unknown timezone cannot be ingested")
        if self.timezone_status == "DECLARED_UTC" and self.origin_kind != "SIMULATED":
            raise ValueError("declared UTC is for synthetic sources")
        if self.timezone_status == "ASSUMED" and (self.source_kind != "REPLAYED" or self.timestamp_origin != "REPLAY_ASSUMPTION"):
            raise ValueError("timezone assumption requires replay provenance")
        if self.source_kind == "REPLAYED" and (not self.origin_transformer_id or not self.replay_run_id):
            raise ValueError("replay lineage required")
        if self.measurement_side not in ("LV", "HV", "UNKNOWN"):
            raise ValueError("invalid measurement side")
        if set(self.field_units) != set(FIELDS) or set(self.field_verification) != set(FIELDS):
            raise ValueError("complete canonical field provenance required")
        for name in FIELDS:
            status = self.field_verification[name]
            if status not in ("SYNTHETIC", "VERIFIED", "UNVERIFIED") or not self.field_units[name]:
                raise ValueError("invalid field verification")
            if status == "SYNTHETIC" and self.origin_kind != "SIMULATED":
                raise ValueError("synthetic units need synthetic origin")
            if status != "UNVERIFIED" and self.field_units[name] not in ALLOWED_UNITS[name]:
                raise ValueError(f"unsupported unit for {name}")
        return self


UNITS = dict(zip(FIELDS, ["V"] * 3 + ["A"] * 4 + ["DEG_C", "STATUS", "DEG_C", "percent"] + ["STATUS"] * 3 + ["kW", "kVA", "kVAr", "kWh"] + ["1"] * 3))
ALLOWED_UNITS = {k: {v} for k, v in UNITS.items()}
for _name in ("oil_temperature", "ambient_temperature", "winding_temperature", "oil_level"):
    ALLOWED_UNITS[_name].add("SOURCE_UNIT")
for _name in ("power_factor_l1", "power_factor_l2", "power_factor_l3"):
    ALLOWED_UNITS[_name].add("dimensionless")


def acquisition(*, source_name="fictional-simulator", sequence=0, interval=5, gateway_id=None, map_version=None):
    return dict(source_kind="SIMULATED", source_name=source_name, origin_kind="SIMULATED",
                origin_transformer_id=None, replay_run_id=None, gateway_id=gateway_id,
                timestamp_origin="SOURCE_SNAPSHOT", timezone_status="DECLARED_UTC",
                field_units=UNITS.copy(), field_verification={k: "SYNTHETIC" for k in FIELDS},
                measurement_side="LV", map_version=map_version, snapshot_id=None,
                sequence=sequence, expected_interval_seconds=interval)


def identify(record):
    """Use the frozen H01/H00 implementation, never a transport-specific hash."""
    record.acquisition["snapshot_id"] = payload_hash(record.model_dump(mode="json"))
    return record


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
