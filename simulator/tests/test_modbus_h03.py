from datetime import datetime, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import pytest
from pymodbus.client import ModbusTcpClient
from simulator.generator import SyntheticGenerator
from simulator.register_map import encode, decode, load_map, words
from simulator.modbus_bridge import SnapshotPoller, SnapshotError
from simulator.modbus_server import SimulationServer

START=datetime(2026,10,9,tzinfo=timezone.utc)


def test_encoding_signed_q_quality_counter_and_timestamp(tmp_path):
    record=SyntheticGenerator().generate(START,1)[0]
    record.reactive_power_total=-12.345
    record.current_l1=0
    record.current_l2=None
    record.energy_kwh=4294967.234567
    registers=encode(record,1)
    decoded=decode(registers,transformer_id="TX-001",unit_id=1,gateway_id="GW")
    assert decoded.timestamp == START
    assert decoded.reactive_power_total == -12.345
    assert decoded.current_l1 == 0
    assert decoded.current_l2 is None
    assert decoded.energy_kwh == pytest.approx(record.energy_kwh,abs=1e-6)
    record.energy_kwh=2  # reset passes through; no invented energy increment
    assert decode(encode(record,1),transformer_id="TX-001",unit_id=1,gateway_id="GW").energy_kwh == 2
    with pytest.raises(ValueError,match="mismatch"):
        decode(registers,transformer_id="OTHER",unit_id=1,gateway_id="GW")
    with pytest.raises(ValueError,match="unit"):
        decode(registers,transformer_id="TX-001",unit_id=2,gateway_id="GW")
    corrupt=registers.copy()
    corrupt[0]=99
    with pytest.raises(ValueError,match="map"):
        decode(corrupt,transformer_id="TX-001",unit_id=1,gateway_id="GW")
    entry=next(e for e in load_map()["fields"] if e["field"] == "current_l2")
    corrupt=registers.copy()
    corrupt[entry["address"]:entry["address"]+2]=words(10,2)
    with pytest.raises(ValueError,match="quality"):
        decode(corrupt,transformer_id="TX-001",unit_id=1,gateway_id="GW")
    spec=load_map()
    spec["fields"][0]["multiplier"]=0
    path=tmp_path/"bad.json"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match="altered"):
        load_map(path)


@pytest.fixture
def loopback_server(tmp_path):
    config=json.loads((files("simulator") / "config/server-demo-25.json").read_text())
    config["assets"]=config["assets"][:2]
    config["interval_seconds"]=3600  # stable snapshot during acceptance reads
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    config["port"]=port
    path=tmp_path/"server.json"
    path.write_text(json.dumps(config))
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    process=subprocess.Popen([sys.executable,"-m","simulator.cli","modbus-server","--config",str(path)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
    client=ModbusTcpClient("127.0.0.1",port=port,timeout=.1,retries=0)
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if process.poll() is not None:
                stdout,stderr=process.communicate()
                pytest.fail(f"server startup failed: {stderr.decode()}")
            if client.connect():
                break
            time.sleep(.05)
        else:
            pytest.fail("loopback server startup timed out")
        client.close()
        yield config,process
    finally:
        client.close()
        process.terminate()
        process.communicate(timeout=10)


def test_real_loopback_independent_fc04_and_read_only(loopback_server):
    config,process=loopback_server
    asset=config["assets"][0]
    expected=SimulationServer(config).snapshots[asset["transformer_id"]]
    client=ModbusTcpClient("127.0.0.1",port=config["port"],timeout=1,retries=0)
    assert client.connect()
    try:
        response=client.read_input_registers(0,count=load_map()["register_count"],slave=asset["unit_id"])
        assert not response.isError()
        assert response.function_code == 4
        assert response.registers == encode(expected,asset["unit_id"])
        decoded=decode(response.registers,transformer_id=asset["transformer_id"],unit_id=asset["unit_id"],gateway_id="GW")
        for entry in load_map()["fields"]:
            name=entry["field"]
            original=getattr(expected,name)
            if original is None:
                assert getattr(decoded,name) is None
            else:
                assert getattr(decoded,name) == pytest.approx(original,abs=entry["multiplier"] / 2 + 1e-10)
        assert client.read_holding_registers(0,count=1,slave=asset["unit_id"]).isError()
        # Rejection tested only against our fictional loopback datastore.
        assert client.write_register(0,123,slave=asset["unit_id"]).isError()
        assert client.read_input_registers(0,count=1,slave=247).isError()
        assert client.read_input_registers(999,count=1,slave=asset["unit_id"]).isError()
        evidence={"pymodbus":"3.6.9","host":"127.0.0.1","port":config["port"],"function_code":4,
            "address":0,"count":len(response.registers),"unit_id":asset["unit_id"],
            "registers":response.registers,"original":expected.model_dump(mode="json"),"decoded":decoded.model_dump(mode="json")}
        if os.environ.get("H03_EVIDENCE_DIR"):
            path=Path(os.environ["H03_EVIDENCE_DIR"])
            path.mkdir(parents=True,exist_ok=True)
            (path/"loopback-fc04.json").write_text(json.dumps(evidence,indent=2))
    finally:
        client.close()
    # Separate bridge client also reads real FC04 TCP frames.
    bridge_asset={**asset,"host":"127.0.0.1","port":config["port"]}
    poller=SnapshotPoller(bridge_asset,"GW",timeout=1)
    try:
        record=poller.poll()
        assert record.transformer_id == asset["transformer_id"]
        assert poller.status["last_success_at"]
        assert record.timestamp == expected.timestamp
        assert record.acquisition["map_version"] == "fictional-lv-v1"
    finally:
        poller.close()


class FakeResponse:
    def __init__(self,registers): self.registers=registers
    def isError(self): return False


class TornClient:
    def __init__(self,registers,torn=True):
        self.registers=registers
        self.torn=torn
        self.calls=0
        self.connects=0
    def connect(self):
        self.connects+=1
        return True
    def close(self): pass
    def read_input_registers(self,address,count,slave):
        self.calls+=1
        result=self.registers[address:address+count]
        if self.torn and address==2 and self.calls%4==0:
            result=words(99,2)
        return FakeResponse(result)


def test_torn_snapshot_bounded_retry_and_reconnect():
    registers=encode(SyntheticGenerator().generate(START,1)[0],1)
    client=TornClient(registers)
    poller=SnapshotPoller({"transformer_id":"TX-001","unit_id":1,"host":"127.0.0.1"},"GW",client=client,retries=2)
    with pytest.raises(SnapshotError,match="TORN"):
        poller.poll()
    assert client.calls == 8  # sequence/two snapshot blocks/sequence × two attempts
    assert poller.status["last_success_at"] is None
    client.torn=False
    assert poller.poll().timestamp == START
    assert poller.status["reconnects"] == 3


def test_real_connection_timeout_bounded():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
        # Bound but not listening: real connection refused, no fake client.
        poller=SnapshotPoller({"transformer_id":"X","unit_id":1,"host":"127.0.0.1","port":port},"GW",timeout=.1,retries=2)
        start=time.monotonic()
        with pytest.raises(SnapshotError): poller.poll()
        assert time.monotonic()-start < 3
        assert poller.status["failures"] == 2
        assert poller.status["last_success_at"] is None


def test_real_disconnect_restart_and_reconnect(loopback_server):
    config, process = loopback_server
    asset = {**config["assets"][0], "host":"127.0.0.1", "port":config["port"]}
    poller = SnapshotPoller(asset,"GW",timeout=.2,retries=1)
    initial = poller.poll()
    process.terminate()
    process.communicate(timeout=10)
    with pytest.raises(SnapshotError):
        poller.poll()
    assert poller.status["connected"] is False
    last_success = poller.status["last_success_at"]
    restarted = subprocess.Popen(process.args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        deadline = time.monotonic()+20
        while True:
            try:
                restored = poller.poll()
                break
            except SnapshotError:
                if restarted.poll() is not None or time.monotonic() >= deadline:
                    pytest.fail("real server failed to reconnect")
                time.sleep(.05)
        assert restored.model_dump_json() == initial.model_dump_json()
        assert restored.timestamp == initial.timestamp  # gateway time is separate
        assert poller.status["last_success_at"] != last_success
        assert poller.status["reconnects"] >= 2
    finally:
        poller.close()
        restarted.terminate()
        restarted.communicate(timeout=10)


def test_server_refuses_public_binding():
    config=json.loads((files("simulator") / "config/server-demo-25.json").read_text())
    config["host"]="0.0.0.0"
    with pytest.raises(ValueError,match="loopback"):
        SimulationServer(config)
