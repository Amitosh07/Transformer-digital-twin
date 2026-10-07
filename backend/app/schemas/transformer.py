"""Asset identity and nullable nameplate configuration; ratings have no defaults."""

from pydantic import ConfigDict, Field

from app.schemas.common import CanonicalModel, FiniteFloat, UtcDatetime


class NameplateFields(CanonicalModel):
    rated_power_kva: FiniteFloat | None = None
    rated_voltage_hv: FiniteFloat | None = None
    rated_voltage_lv: FiniteFloat | None = None
    rated_current_a: FiniteFloat | None = None
    cooling_class: str | None = Field(default=None, max_length=128)
    oil_type: str | None = Field(default=None, max_length=128)


class TransformerIn(NameplateFields):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class TransformerOut(TransformerIn):
    model_config = ConfigDict(from_attributes=True)

    created_at: UtcDatetime
    updated_at: UtcDatetime


class TransformerPatch(NameplateFields):
    name: str | None = Field(default=None, min_length=1, max_length=255)
