from click.testing import CliRunner
from simulator.cli import cli
import json


def test_new_commands_and_legacy_flags():
    runner=CliRunner()
    for command in ("modbus-server","modbus-bridge","replay-canonical","generate","stream","replay","inject"):
        result=runner.invoke(cli,[command,"--help"])
        assert result.exit_code == 0, result.output
    args=["generate","--count","2","--interval","5","--seed","42","--transformer-id","CLI-FICTIONAL","--start-utc","2026-10-09T00:00:00Z"]
    a,b=runner.invoke(cli,args),runner.invoke(cli,args)
    assert a.exit_code == b.exit_code == 0
    assert a.output == b.output
    rows=[json.loads(line) for line in a.output.splitlines()]
    assert len(rows) == 2
    assert rows[0]["acquisition"]["source_kind"] == "SIMULATED"
    assert rows[0]["energy_kwh"] == 0


def test_unbounded_stream_publishes_incrementally(monkeypatch):
    import simulator.streaming
    published=[]
    class Publisher:
        def __init__(self,**kwargs): pass
        def publish(self,record):
            published.append(record)
            if len(published) == 3:
                raise KeyboardInterrupt()
        def close(self): pass
    monkeypatch.setattr(simulator.streaming,"StreamPublisher",Publisher)
    monkeypatch.setattr("simulator.cli.time.sleep",lambda seconds:None)
    # Explicit single-asset mode remains incremental; omitted ID now selects
    # the operational fleet's existing Modbus bridge rather than TX-001.
    result=CliRunner().invoke(cli,["stream","--transformer-id","TX-001","--count","0","--interval","5","--start-utc","2026-10-09T00:00:00Z"])
    assert result.exit_code == 0, result.output
    assert [r.acquisition["sequence"] for r in published] == [0,1,2]


def test_replay_requires_explicit_destination_and_run():
    result=CliRunner().invoke(cli,["replay-canonical"])
    assert result.exit_code != 0
    assert "Missing option" in result.output
