"""The fictional FC04 map codec. Wire data never implies verified live units."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from importlib.resources import files
import json
from ml.pipeline.identity import FIELDS, PROTECTION
from .schema import TransformerRecord, acquisition, identify

VERSION = "fictional-lv-v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def load_map(path=None):
    spec = json.loads((files("simulator") / "config/register-map-v1.json").read_text(encoding="utf-8") if path is None else path.read_text(encoding="utf-8"))
    reference = json.loads((files("simulator") / "config/register-map-v1.json").read_text(encoding="utf-8"))
    # A version identifies the entire encoding, not a permission to change scale.
    if spec != reference or spec["map_version"] != VERSION:
        raise ValueError("unknown or altered register-map version")
    return spec


def words(number, count, signed=False):
    raw = int(number).to_bytes(count * 2, "big", signed=signed)
    return [int.from_bytes(raw[i:i+2], "big") for i in range(0, len(raw), 2)]


def integer(registers, signed=False):
    if any(type(r) is not int or not 0 <= r <= 65535 for r in registers):
        raise ValueError("invalid register word")
    return int.from_bytes(b"".join(r.to_bytes(2, "big") for r in registers), "big", signed=signed)


def text_words(value, count):
    raw = value.encode("utf-8")
    if not raw or len(raw) > count * 2 or b"\x00" in raw:
        raise ValueError("invalid map text length")
    raw = raw.ljust(count * 2, b"\x00")
    return [int.from_bytes(raw[i:i+2], "big") for i in range(0, len(raw), 2)]


def read_text(registers):
    raw = b"".join(r.to_bytes(2, "big") for r in registers)
    head, _, padding = raw.partition(b"\x00")
    if any(padding):
        raise ValueError("invalid text padding")
    return head.decode("utf-8")


def encode(record, unit_id, spec=None):
    spec = spec or load_map()
    if spec != load_map():
        raise ValueError("unknown or altered register-map version")
    record = TransformerRecord.model_validate(record.model_dump())
    if not 1 <= unit_id <= 247 or not record.acquisition or record.acquisition["origin_kind"] != "SIMULATED":
        raise ValueError("fictional map requires simulated configuration")
    registers = [0] * spec["register_count"]
    registers[0] = 1
    registers[1] = unit_id
    sequence = record.acquisition["sequence"]
    registers[2:4] = words(sequence, 2)
    diff = record.timestamp.astimezone(timezone.utc) - EPOCH
    micros = (diff.days * 86400 + diff.seconds) * 1000000 + diff.microseconds
    registers[4:8] = words(micros, 4)
    registers[10:42] = text_words(record.transformer_id, 32)
    registers[42:58] = text_words(record.scenario_id or "SCN_HEALTHY_01", 16)
    quality = 0
    for entry in spec["fields"]:
        value = getattr(record, entry["field"])
        # UNVERIFIED/unknown input is unavailable on this declared-unit map.
        if record.acquisition["field_verification"][entry["field"]] == "UNVERIFIED":
            value = None
        if value is None:
            continue  # zero storage with absent quality is NOT numeric zero
        if record.acquisition["field_units"][entry["field"]] != entry["unit"]:
            raise ValueError("input unit differs from map")
        number = int((Decimal(str(value)) / Decimal(str(entry["multiplier"]))).to_integral_value(rounding=ROUND_HALF_EVEN))
        quality |= 1 << entry["quality_bit"]
        a, n = entry["address"], entry["count"]
        registers[a:a+n] = words(number, n, entry["signed"])
    registers[8:10] = words(quality, 2)
    return registers


def decode(registers, *, transformer_id, unit_id, gateway_id, expected_interval_seconds=5, spec=None):
    spec = spec or load_map()
    if spec != load_map():
        raise ValueError("unknown or altered register-map version")
    if len(registers) != spec["register_count"] or registers[0] != 1 or registers[1] != unit_id:
        raise ValueError("invalid length/map/unit ID")
    integer(registers)  # check all word types/ranges before interpreting anything
    if read_text(registers[10:42]) != transformer_id:
        raise ValueError("asset/unit ID mismatch")
    quality = integer(registers[8:10])
    if quality >> len(FIELDS):
        raise ValueError("unknown quality bits")
    values = {}
    for entry in spec["fields"]:
        a, n = entry["address"], entry["count"]
        name = entry["field"]
        value = integer(registers[a:a+n], entry["signed"])
        if not quality & (1 << entry["quality_bit"]):
            if value != 0:
                raise ValueError("missing quality with nonzero sentinel")
            values[name] = None
        else:
            values[name] = int(value) if name in PROTECTION else float(Decimal(value) * Decimal(str(entry["multiplier"])))
    timestamp = EPOCH + timedelta(microseconds=integer(registers[4:8]))
    acq = acquisition(source_name="fictional-modbus", gateway_id=gateway_id, map_version=VERSION,
                      sequence=integer(registers[2:4]), interval=expected_interval_seconds)
    return identify(TransformerRecord(transformer_id=transformer_id, timestamp=timestamp,
        schema_version="1.1.0", source_name="fictional-modbus", scenario_id=read_text(registers[42:58]),
        acquisition=acq, **values))
