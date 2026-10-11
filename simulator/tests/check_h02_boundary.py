"""Standalone NEW H03 producer/H02 parser check, run in H02's installed venv.

No SQL/broker evidence is claimed. Does not rerun H02 or H01 test suites.
"""
from datetime import datetime,timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from ml.pipeline.identity import payload_hash,serialize
from simulator.generator import SyntheticGenerator
from simulator.register_map import encode,decode
from simulator.replay import CanonicalReplay
from app.mqtt.message_handler import parse_message,MessageRejected


def main():
    source=SyntheticGenerator(interval_s=5).generate(datetime(2026,10,9,tzinfo=timezone.utc),1)[0]
    bridge=decode(encode(source,1),transformer_id=source.transformer_id,unit_id=1,gateway_id="H03-GW")
    rows=[source.model_dump(mode="json"),bridge.model_dump(mode="json")]
    with TemporaryDirectory() as directory:
        path=Path(directory)/"source.jsonl"
        path.write_text(source.model_dump_json())
        rows.extend(CanonicalReplay(path,"H03-REPLAY","H03-run").records())
        for row in rows:
            encoded=serialize(row).encode("utf-8")
            parsed=parse_message(f"transformer/{row['transformer_id']}/telemetry",encoded)[0]
            assert payload_hash(parsed.semantic_record()) == row["acquisition"]["snapshot_id"]
            assert parsed.acquisition.field_units["oil_level"] == "percent"
            assert parsed.winding_temperature is None
        try:
            parse_message("transformer/OTHER/telemetry",serialize(rows[1]).encode())
        except MessageRejected as exc:
            assert exc.reason == "TOPIC_ID_MISMATCH"
        else:
            raise AssertionError("topic/payload mismatch accepted")
    print("PASSED: generated, decoded and replayed H03 payloads accepted by actual H02 MQTT parser with exact semantic hashes; mismatch rejected. No SQL or broker test.")


if __name__ == "__main__":
    main()
