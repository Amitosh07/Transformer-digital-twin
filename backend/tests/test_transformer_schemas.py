import pytest
from pydantic import ValidationError

from app.schemas.transformer import TransformerIn, TransformerOut, TransformerPatch

NAMEPLATE = [
    "rated_power_kva",
    "rated_voltage_hv",
    "rated_voltage_lv",
    "rated_current_a",
    "cooling_class",
    "oil_type",
]
NUMERIC = NAMEPLATE[:4]


def test_nameplate_is_nullable_without_defaults() -> None:
    for record in [TransformerIn(id="TX-001", name="Transformer"), TransformerPatch()]:
        for name in NAMEPLATE:
            assert getattr(record, name) is None
    assert TransformerPatch().model_dump(exclude_unset=True) == {}
    assert TransformerPatch(rated_power_kva=None).model_dump(exclude_unset=True) == {
        "rated_power_kva": None,
    }


@pytest.mark.parametrize("schema", [TransformerIn, TransformerOut, TransformerPatch])
@pytest.mark.parametrize("field", NUMERIC)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nameplate_floats_are_finite(
    schema: type[TransformerIn | TransformerOut | TransformerPatch], field: str, value: float
) -> None:
    payload = {"id": "TX-001", "name": "Transformer"}
    if schema is TransformerOut:
        payload |= {"created_at": "2026-10-06T00:00:00Z", "updated_at": "2026-10-06T00:00:00Z"}
    elif schema is TransformerPatch:
        payload = {}
    with pytest.raises(ValidationError):
        schema(**payload, **{field: value})


def test_transformer_out_timestamps_are_aware() -> None:
    with pytest.raises(ValidationError):
        TransformerOut(
            id="TX-001",
            name="Transformer",
            created_at="2026-10-06T00:00:00",
            updated_at="2026-10-06T00:00:00Z",
        )
