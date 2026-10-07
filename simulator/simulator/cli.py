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

from .faults import SCENARIO_CATALOGUE, FaultInjector
from .generator import SyntheticGenerator
from .schema import TransformerConfig, TransformerRecord


def _default_start() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


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
def generate(count: int, interval: int, transformer_id: str, seed: int, output: Optional[str]) -> None:
    """Generate synthetic canonical telemetry (normal operation)."""
    cfg = TransformerConfig(transformer_id=transformer_id)
    gen = SyntheticGenerator(config=cfg, seed=seed, interval_s=interval)
    records = gen.generate(start=_default_start(), count=count)
    _dump_records(records, output)


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

@cli.command()
@click.argument("csv_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--speed", default=10.0, help="Playback speed multiplier (1=realtime).")
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--output", "-o", default=None, help="Output file (default: stdout).")
def replay(csv_files: tuple[str, ...], speed: float, transformer_id: str, output: Optional[str]) -> None:
    """Replay historical Kaggle CSVs through the canonical adapter."""
    from .replay import ReplayEngine

    engine = ReplayEngine(
        csv_paths=list(csv_files),
        transformer_id=transformer_id,
        speed_multiplier=speed,
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
def inject(scenario: str, count: int, transformer_id: str, seed: int, output: Optional[str]) -> None:
    """Generate records with a fault scenario injected."""
    scenario = scenario.upper()
    if scenario not in SCENARIO_CATALOGUE:
        click.echo(f"Unknown scenario: {scenario}.  Use 'simulator scenarios' to list.", err=True)
        sys.exit(1)

    cfg = TransformerConfig(transformer_id=transformer_id)
    gen = SyntheticGenerator(config=cfg, seed=seed)
    base_records = gen.generate(start=_default_start(), count=count)

    injector = FaultInjector(seed=seed)
    mutated: list[TransformerRecord] = []
    for rec in base_records:
        m, meta = injector.inject(rec, scenario)
        mutated.append(m)

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
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--seed", default=42, help="RNG seed.")
@click.option("--csv", "csv_files", multiple=True, type=click.Path(exists=True), help="CSV for replay mode.")
@click.option("--speed", default=10.0, help="Replay speed multiplier.")
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
) -> None:
    """Stream live canonical telemetry via MQTT or HTTP."""
    from .streaming import StreamPublisher

    pub = StreamPublisher(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        http_url=http_url,
        source_name="mqtt-simulator" if mqtt_host else "simulator",
    )

    injector: Optional[FaultInjector] = None
    if scenario:
        scenario = scenario.upper()
        if scenario not in SCENARIO_CATALOGUE:
            click.echo(f"Unknown scenario: {scenario}", err=True)
            sys.exit(1)
        injector = FaultInjector(seed=seed)

    if mode == "replay" and csv_files:
        from .replay import ReplayEngine
        engine = ReplayEngine(list(csv_files), transformer_id, speed)
        records = engine.all_records()
    else:
        cfg = TransformerConfig(transformer_id=transformer_id)
        gen = SyntheticGenerator(config=cfg, seed=seed, interval_s=interval)
        n = count if count > 0 else 999_999
        records = gen.generate(start=_default_start(), count=n)

    sent = 0
    try:
        for rec in records:
            if injector and scenario:
                rec, _ = injector.inject(rec, scenario)

            pub.publish(rec)
            sent += 1
            click.echo(f"[{sent}] {rec.timestamp} → published", err=True)

            if 0 < count <= sent:
                break
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

    for sc_name in demo_scenarios:
        click.echo(f"\n{'=' * 60}")
        click.echo(f"  DEMO SCENARIO: {sc_name}")
        click.echo(f"{'=' * 60}")

        gen = SyntheticGenerator(config=cfg, seed=42)
        base_records = gen.generate(start=_default_start(), count=records_per_scenario)

        injector = FaultInjector(seed=99)
        mutated: list[TransformerRecord] = []
        for rec in base_records:
            m, meta = injector.inject(rec, sc_name)
            mutated.append(m)

        click.echo(f"  Scenario ID : {meta.scenario_id}")
        click.echo(f"  Severity    : {meta.severity}")
        click.echo(f"  Injected    : {meta.injected_variables}")
        click.echo(f"  Expected    : {meta.expected_response}")
        click.echo(f"  Records     : {len(mutated)}")

        pub.publish_batch(mutated)
        click.echo(f"  ✓ Published to backend.")
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
@click.option("--transformer-id", default="TX-001", help="Asset ID.")
@click.option("--seed", default=42, help="RNG seed.")
def seed(http_url: str, count: int, transformer_id: str, seed: int) -> None:
    """Bulk-seed the backend with synthetic normal-operation data."""
    from .streaming import HttpPublisher

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


if __name__ == "__main__":
    cli()
