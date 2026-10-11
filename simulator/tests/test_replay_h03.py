from datetime import datetime, timezone
from decimal import Decimal
import json
import httpx
import pandas as pd
import pytest
from simulator.generator import SyntheticGenerator
from simulator.replay import CanonicalReplay, ReplayEngine, shared_adapter
from ml.pipeline.identity import serialize, payload_hash

START = datetime(2026,10,9,tzinfo=timezone.utc)


def test_canonical_replay_preserves_times_precision_lineage(tmp_path):
    records = [r.model_dump(mode="json") for r in SyntheticGenerator(interval_s=5).generate(START,3)]
    records[1]["energy_kwh"] = Decimal("0.1234567890123456789")
    records[1]["acquisition"]["snapshot_id"] = payload_hash(records[1])
    source = tmp_path / "input.jsonl"
    content = "\n".join(serialize(r) for r in records)
    source.write_text(content)
    engine = CanonicalReplay(source, "REPLAY-A", "run-one", speed=10)
    sleeps = []
    replay = list(engine.playback(sleeper=sleeps.append))
    assert sleeps == [.5,.5]
    assert [r["timestamp"] for r in replay] == [r["timestamp"] for r in records]
    assert replay[1]["energy_kwh"] == Decimal("0.1234567890123456789")
    assert source.read_text() == content
    assert all(r["acquisition"]["source_kind"] == "REPLAYED" for r in replay)
    assert all(r["acquisition"]["origin_kind"] == "SIMULATED" for r in replay)
    assert all(r["acquisition"]["origin_transformer_id"] == "TX-001" for r in replay)
    another = list(CanonicalReplay(source,"REPLAY-B","run-two").records())
    assert {r["acquisition"]["snapshot_id"] for r in replay}.isdisjoint(r["acquisition"]["snapshot_id"] for r in another)
    assert [r["acquisition"]["snapshot_id"] for r in replay] == [r["acquisition"]["snapshot_id"] for r in engine.records()]
    with pytest.raises(ValueError,match="separate"):
        list(CanonicalReplay(source,"TX-001","run-one").records())


def test_legacy_assumptions_and_changed_duplicates(tmp_path):
    source = tmp_path / "legacy.jsonl"
    row = {"transformer_id":"REAL-UNKNOWN", "timestamp":"2026-10-09T00:00:00", "winding_temperature":1, "active_power_total":10}
    source.write_text(json.dumps(row)+"\n")
    with pytest.raises(ValueError,match="timezone"):
        list(CanonicalReplay(source,"REPLAY-X","r").records())
    result = list(CanonicalReplay(source,"REPLAY-X","r",timezone_assumption="UTC").records())[0]
    assert result["winding_temperature"] == 1
    assert result["acquisition"]["field_units"]["active_power_total"] == "UNKNOWN"
    assert result["acquisition"]["timezone_status"] == "ASSUMED"
    assert result["acquisition"]["origin_kind"] == "UNKNOWN"
    source.write_text(json.dumps(row)+"\n"+json.dumps(row)+"\n")
    assert len(list(CanonicalReplay(source,"REPLAY-X","r",timezone_assumption="UTC").records())) == 1
    row["oil_temp_trip"] = 1
    source.write_text(source.read_text()+json.dumps(row)+"\n")
    with pytest.raises(ValueError,match="changed duplicate"):
        list(CanonicalReplay(source,"REPLAY-X","r",timezone_assumption="UTC").records())


def test_real_shared_csv_adapter_duplicate_alignment_wti_and_power(tmp_path):
    adapter = shared_adapter()
    paths=[]
    for name, rules in adapter.AGGREGATION_RULES.items():
        columns = [col for values in rules.values() for col in values]
        if name == "Overview.csv":
            columns.append("WTI")
        rows = [{"DeviceTimeStamp":"2026-10-09 00:00:00", **{key:0 for key in columns}} for _ in range(2)]
        if name == "Overview.csv":
            rows[0]["WTI"], rows[1]["WTI"] = 0,1
            rows[1]["OTI_T"] = 1
        if name == "TotalPower.csv":
            for row in rows:
                row.update(KW=10,KVA=12,KVAR=6)
            rows[0]["KWH"], rows[1]["KWH"] = 100,101
        path=tmp_path/name
        pd.DataFrame(rows).to_csv(path,index=False)
        paths.append(path)
    with pytest.raises(ValueError,match="timezone"):
        ReplayEngine(paths, "R")
    engine=ReplayEngine(paths,"R",timezone_assumption="UTC")
    record=engine.all_records()[0]
    assert engine.record_count == 1  # no Cartesian duplicate multiplication
    assert record.winding_temperature is None
    assert record.oil_temp_trip == 1
    assert (record.active_power_total,record.apparent_power_total,record.reactive_power_total,record.energy_kwh) == (10,12,6,101)
    assert record.acquisition["field_verification"]["active_power_total"] == "UNVERIFIED"
    assert record.acquisition["field_units"]["active_power_total"] == "UNKNOWN"


def test_destination_registry_and_conflicting_live_stream(tmp_path):
    engine=CanonicalReplay(tmp_path/"unused","R","r")
    first={"acquisition":{"origin_transformer_id":"ORIGIN"}}
    def handler(request):
        if request.url.path.endswith("latest"):
            return httpx.Response(200,json={"telemetry":{"acquisition":{"source_kind":"LIVE"}}})
        return httpx.Response(200,json={"id":"R"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match="conflicting"):
            engine.validate_destination(client,"http://test",first)
