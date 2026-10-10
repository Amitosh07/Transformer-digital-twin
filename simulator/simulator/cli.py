"""
Simulator CLI — simulator_README §12, §15.

Provides one-command entry points:

  simulator generate    – emit synthetic canonical records (stdout / JSON)
  simulator replay      – replay historical CSV through the adapter
  simulator inject      – run a named fault scenario
  simulator stream      – continuous live simulation (MQTT / HTTP)
  simulator demo        – run all demo scenarios in sequence
  simulator seed        – bulk-seed the backend via HTTP
  simulator scenarios   – list available fault scenarios
  simulator reset       – request a demo reset from the backend
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import time
from pathlib import Path
from typing import Optional

import click

from .faults import SCENARIO_CATALOGUE
from .generator import SyntheticGenerator
from .schema import TransformerConfig, TransformerRecord


def _default_start() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_start(value):
    from ml.pipeline.identity import utc
    return _default_start() if value is None else _dt.datetime.fromisoformat(utc(value).replace("Z", "+00:00"))


def _dump_records(records: list[TransformerRecord], output: Optional[str]) -> None:
    """Write records as newline-delimited JSON."""
    data = [json.loads(r.model_dump_json()) for r in records]
    text = "\n".join(json.dumps(d) for d in data) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Wrote {len(records)} records to {output}")
    else:
        sys.stdout.write(text)


@click.group()
def cli() -> None:
    """Transformer Digital Twin — Simulator CLI."""
    pass


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------

@cli.command()
@click.option("--count", "-n", default=60, help="Number of records to generate.")
@click.option("--interval", default=60, help="Seconds between observations.")
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--seed", default=42, help="RNG seed for reproducibility.")
@click.option("--output", "-o", default=None, help="Output file (default: stdout).")
@click.option("--start-utc", default=None, help="Explicit aware event start for repeatability.")
def generate(count: int, interval: int, transformer_id: str, seed: int, output: Optional[str], start_utc=None) -> None:
    """Generate synthetic canonical telemetry (normal operation)."""
    cfg = TransformerConfig(transformer_id=transformer_id)
    gen = SyntheticGenerator(config=cfg, seed=seed, interval_s=interval)
    records = gen.generate(start=_parse_start(start_utc), count=count)
    _dump_records(records, output)


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

@cli.command()
@click.argument("csv_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--speed", default=10.0, help="Playback speed multiplier (1=realtime).")
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--output", "-o", default=None, help="Output file (default: stdout).")
@click.option("--timezone", default=None, help="Explicit source timezone assumption, e.g. UTC.")
@click.option("--origin-transformer-id", default="RAW-UNKNOWN")
@click.option("--run-id", default="legacy-csv-replay")
@click.option("--adapter-path", default=None, type=click.Path(exists=True))
def replay(csv_files: tuple[str, ...], speed: float, transformer_id: str, output: Optional[str], timezone=None, origin_transformer_id="RAW-UNKNOWN", run_id="legacy-csv-replay", adapter_path=None) -> None:
    """Replay historical Kaggle CSVs through the canonical adapter."""
    from .replay import ReplayEngine

    engine = ReplayEngine(
        csv_paths=list(csv_files),
        transformer_id=transformer_id,
        speed_multiplier=speed,
        timezone_assumption=timezone, origin_transformer_id=origin_transformer_id,
        replay_run_id=run_id, adapter_path=adapter_path,
    )
    click.echo(f"Loaded {engine.record_count} records at {speed}× speed.", err=True)
    records = engine.all_records()
    _dump_records(records, output)


# --------------------------------------------------------------------------
# inject
# --------------------------------------------------------------------------

@cli.command()
@click.option("--scenario", "-s", required=True, help="Scenario name (see 'scenarios').")
@click.option("--count", "-n", default=10, help="Records to generate with fault applied.")
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--seed", default=42, help="RNG seed.")
@click.option("--output", "-o", default=None, help="Output file (default: stdout).")
@click.option("--start-utc", default=None)
def inject(scenario: str, count: int, transformer_id: str, seed: int, output: Optional[str], start_utc=None) -> None:
    """Generate records with a fault scenario injected."""
    scenario = scenario.upper()
    if scenario not in SCENARIO_CATALOGUE:
        click.echo(f"Unknown scenario: {scenario}.  Use 'simulator scenarios' to list.", err=True)
        sys.exit(1)

    cfg = TransformerConfig(transformer_id=transformer_id)
    gen = SyntheticGenerator(config=cfg, seed=seed)
    mutated = gen.generate(start=_parse_start(start_utc), count=count, scenario=scenario)
    meta = SCENARIO_CATALOGUE[scenario]

    click.echo(f"Scenario: {meta.scenario_id} — {meta.description}", err=True)
    click.echo(f"Severity: {meta.severity}", err=True)
    click.echo(f"Injected: {meta.injected_variables}", err=True)
    click.echo(f"Expected: {meta.expected_response}", err=True)
    _dump_records(mutated, output)


# --------------------------------------------------------------------------
# stream
# --------------------------------------------------------------------------

@cli.command()
@click.option("--mode", type=click.Choice(["synthetic", "replay"]), default="synthetic")
@click.option("--scenario", "-s", default=None, help="Fault scenario to inject (optional).")
@click.option("--mqtt-host", default=None, help="MQTT broker host (omit for HTTP).")
@click.option("--mqtt-port", default=1883, help="MQTT broker port.")
@click.option("--http-url", default="http://localhost:8001", help="Backend HTTP URL.")
@click.option("--interval", default=5, help="Seconds between transmissions.")
@click.option("--count", "-n", default=0, help="Records to send (0 = infinite).")
@click.option("--transformer-id", default=None, help="Explicit legacy single asset. Omit to poll the operational ten-asset Modbus fleet.")
@click.option("--fleet-bridge-config", default=None, type=click.Path(exists=True), help="Fleet bridge config; native loopback configuration by default.")
@click.option("--seed", default=42, help="RNG seed.")
@click.option("--csv", "csv_files", multiple=True, type=click.Path(exists=True), help="CSV for replay mode.")
@click.option("--speed", default=10.0, help="Replay speed multiplier.")
@click.option("--timezone", default=None)
@click.option("--start-utc", default=None)
def stream(
    mode: str,
    scenario: Optional[str],
    mqtt_host: Optional[str],
    mqtt_port: int,
    http_url: str,
    interval: int,
    count: int,
    transformer_id: str,
    seed: int,
    csv_files: tuple[str, ...],
    speed: float,
    timezone=None,
    start_utc=None,
    fleet_bridge_config=None,
) -> None:
    """Poll the operational Modbus fleet; explicit assets retain MQTT/HTTP streams."""
    from .streaming import StreamPublisher

    if transformer_id is None:
        if mode != 'synthetic' or scenario or count or start_utc or mqtt_host or interval != 5:
            raise click.UsageError('Use --fleet-bridge-config for fleet transport; explicit --transformer-id for legacy single-asset flags/replay')
        from .fleet import DEFAULT_CONFIG
        from .modbus_bridge import run_bridge
        run_bridge(fleet_bridge_config or DEFAULT_CONFIG / 'operational-bridge-native.json')
        return

    pub = StreamPublisher(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        http_url=http_url,
        source_name="mqtt-simulator" if mqtt_host else "simulator",
    )

    if scenario:
        scenario = scenario.upper()
        if scenario not in SCENARIO_CATALOGUE:
            click.echo(f"Unknown scenario: {scenario}", err=True)
            sys.exit(1)

    if mode == "replay" and csv_files:
        from .replay import ReplayEngine
        if scenario:
            raise click.UsageError("historical replay cannot silently acquire simulated faults")
        engine = ReplayEngine(list(csv_files), transformer_id, speed, timezone_assumption=timezone)
        records = engine.replay()
    elif mode == "replay":
        raise click.UsageError("replay mode requires --csv")
    else:
        cfg = TransformerConfig(transformer_id=transformer_id)
        gen = SyntheticGenerator(config=cfg, seed=seed, interval_s=interval)
        records = gen.iter_records(start=_parse_start(start_utc), count=count if count > 0 else None, scenario=scenario or "HEALTHY")

    sent = 0
    try:
        for rec in records:
            pub.publish(rec)
            sent += 1
            click.echo(f"[{sent}] {rec.timestamp} → published", err=True)

            if 0 < count <= sent:
                break
            if mode != "replay":
                time.sleep(interval)

    except KeyboardInterrupt:
        click.echo(f"\nStopped after {sent} records.", err=True)
    finally:
        pub.close()


# --------------------------------------------------------------------------
# demo
# --------------------------------------------------------------------------

@cli.command()
@click.option("--http-url", default="http://localhost:8001", help="Backend HTTP URL.")
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--records-per-scenario", default=10, help="Records per scenario.")
def demo(http_url: str, transformer_id: str, records_per_scenario: int) -> None:
    """Run all demo scenarios (§14) and seed the backend."""
    from .streaming import HttpPublisher

    pub = HttpPublisher(base_url=http_url, source_name="demo")
    cfg = TransformerConfig(transformer_id=transformer_id)

    demo_scenarios = ["HEALTHY", "OVERLOAD", "THERMAL_STRESS", "CURRENT_IMBALANCE", "LOW_OIL_LEVEL"]
    gen = SyntheticGenerator(config=cfg, seed=42)
    event_time = _default_start()

    for sc_name in demo_scenarios:
        click.echo(f"\n{'=' * 60}")
        click.echo(f"  DEMO SCENARIO: {sc_name}")
        click.echo(f"{'=' * 60}")

        mutated = gen.generate(start=event_time, count=records_per_scenario, scenario=sc_name)
        event_time += _dt.timedelta(seconds=records_per_scenario * gen.interval_s)
        meta = SCENARIO_CATALOGUE[sc_name]

        click.echo(f"  Scenario ID : {meta.scenario_id}")
        click.echo(f"  Severity    : {meta.severity}")
        click.echo(f"  Injected    : {meta.injected_variables}")
        click.echo(f"  Expected    : {meta.expected_response}")
        click.echo(f"  Records     : {len(mutated)}")

        pub.publish_batch(mutated)
        click.echo("  ✓ Published to backend.")
        time.sleep(1)  # Brief pause between scenarios

    pub.close()
    click.echo(f"\n{'=' * 60}")
    click.echo("  ALL DEMO SCENARIOS COMPLETE")
    click.echo(f"{'=' * 60}")


# --------------------------------------------------------------------------
# seed
# --------------------------------------------------------------------------

@cli.command()
@click.option("--http-url", default="http://localhost:8001", help="Backend HTTP URL.")
@click.option("--count", "-n", default=1440, help="Number of records (default = 1 day at 1-min).")
@click.option("--transformer-id", default=None, help="Explicit legacy single-asset historical seed. Omit to register only the operational fleet, without generating history.")
@click.option("--fleet-file", default=None, type=click.Path(exists=True), help="Shared fleet manifest.")
@click.option("--seed", default=42, help="RNG seed.")
def seed(http_url: str, count: int, transformer_id: str, seed: int, fleet_file=None) -> None:
    """Register the operational fleet; explicit assets retain historical seeding."""
    from .streaming import HttpPublisher

    if transformer_id is None:
        from .fleet import DEFAULT_FLEET, register_fleet
        register_fleet(http_url, fleet_file or DEFAULT_FLEET)
        click.echo('Registered the configured operational fleet; history was not generated or relabelled.')
        return

    pub = HttpPublisher(base_url=http_url, source_name="seed")
    cfg = TransformerConfig(transformer_id=transformer_id)
    gen = SyntheticGenerator(config=cfg, seed=seed)
    records = gen.generate(start=_default_start() - _dt.timedelta(hours=24), count=count)

    click.echo(f"Seeding {len(records)} records to {http_url}...", err=True)
    # Send in batches of 500
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        pub.publish_batch(batch)
        click.echo(f"  Batch {i // batch_size + 1}: {len(batch)} records sent.", err=True)

    pub.close()
    click.echo(f"✓ Seeded {len(records)} records.", err=True)


# --------------------------------------------------------------------------
# scenarios
# --------------------------------------------------------------------------

@cli.command()
def scenarios() -> None:
    """List all available fault-injection scenarios."""
    for name, meta in SCENARIO_CATALOGUE.items():
        click.echo(f"\n{name}")
        click.echo(f"  ID         : {meta.scenario_id}")
        click.echo(f"  Description: {meta.description}")
        click.echo(f"  Severity   : {meta.severity}")
        click.echo(f"  Injected   : {meta.injected_variables}")
        click.echo(f"  Expected   : {meta.expected_response}")


# --------------------------------------------------------------------------
# reset
# --------------------------------------------------------------------------

@cli.command()
@click.option("--http-url", default="http://localhost:8001", help="Backend HTTP URL.")
@click.option("--token", default="", help="Demo admin token.")
@click.confirmation_option(prompt="This will reset the database. Continue?")
def reset(http_url: str, token: str) -> None:
    """Request a demo reset from the backend (§15)."""
    import httpx

    url = f"{http_url.rstrip('/')}/api/v1/admin/demo/reset"
    headers = {}
    if token:
        headers["X-Admin-Token"] = token

    try:
        resp = httpx.post(url, headers=headers, timeout=30)
        resp.raise_for_status()
        click.echo(f"✓ Demo reset successful: {resp.json()}")
    except httpx.HTTPError as exc:
        click.echo(f"✗ Reset failed: {exc}", err=True)
        sys.exit(1)


@cli.command("modbus-server")
@click.option("--config", required=True, type=click.Path(exists=True))
def modbus_server(config):
    """Run the loopback read-only fictional FC04 server."""
    from .modbus_server import run_server
    run_server(config)


@cli.command("modbus-bridge")
@click.option("--config", required=True, type=click.Path(exists=True))
def modbus_bridge(config):
    """Poll FC04 and deliver through a durable receipt-aware QoS1 spool."""
    from .modbus_bridge import run_bridge
    run_bridge(config)


@cli.command("replay-canonical")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--transformer-id", required=True)
@click.option("--run-id", required=True, help="Immutable replay lineage; use a separate registered asset for each run.")
@click.option("--http-url", required=True)
@click.option("--speed", default=1.0)
@click.option("--timezone", default=None, help="Explicit assumption for legacy/naive sources; never verifies units.")
def replay_canonical(input_path, transformer_id, run_id, http_url, speed, timezone):
    """Replay JSONL to a separate registered asset, preserving event timestamps."""
    import httpx
    from .replay import CanonicalReplay
    from ml.pipeline.identity import serialize
    engine = CanonicalReplay(input_path, transformer_id, run_id, speed, timezone)
    click.echo("Direct HTTP replay: Modbus disconnected/not used. Legacy units remain UNVERIFIED; explicit timezone assumptions are recorded.", err=True)
    with httpx.Client(timeout=10) as client:
        iterator = engine.playback()
        first = next(iterator, None)
        if first is None:
            raise click.ClickException("empty replay input")
        engine.validate_destination(client, http_url, first)
        import itertools
        for record in itertools.chain([first], iterator):
            response = client.post(f"{http_url.rstrip('/')}/api/v1/telemetry",
                content=serialize(record), headers={"Content-Type": "application/json"})
            response.raise_for_status()
            if response.json().get("ingestion_outcome") == "REJECTED_LATE":
                raise click.ClickException("backend rejected late replay observation; stopping run")
            click.echo(f"HTTP accepted {record['acquisition']['snapshot_id']}; source event {record['timestamp']}", err=True)


if __name__ == "__main__":
    cli()
