# H03 — Simulator, read-only Modbus and durable MQTT bridge

Implemented locally on 2026-10-09. Independent source, replay, scheduler,
protocol and delivery-contract checks pass. **Full Modbus→MQTT→PostgreSQL→receipt
acceptance remains BLOCKED**; no backend commit or broker PUBACK was observed.
This is implementation evidence for manual review, not a completed end-to-end
acceptance claim. H00/H01 approval is established by the user; H02's documented
SQL gate has not been bypassed. No next phase, commit, push or merge was performed.

## Preflight and preservation

Actual pre-edit read-only outputs, each exit 0:

```text
git branch --show-current
develop
git rev-parse HEAD
29dcfaf5e12ef50446d1106c4994a721dc802476
git status --short
96 pre-existing modified/untracked files from H00/H01/H02; no simulator changes.
```

Individual pre-existing files were SHA-256 captured in
`$env:TEMP/h03-existing-baseline.json` before edits. Final preservation/scope
verification is recorded below. Verified contract/fixtures, ML and backend,
frontend, root Compose and existing reports were not edited.

## Exact changed paths

Modified:

```text
simulator/pyproject.toml
simulator/simulator/cli.py
simulator/simulator/faults.py
simulator/simulator/generator.py
simulator/simulator/replay.py
simulator/simulator/schema.py
simulator/simulator/streaming.py
```

Created:

```text
simulator/.gitignore
simulator/H03_RUNBOOK.md
simulator/simulator/config/register-map-v1.json
simulator/simulator/config/server-demo-25.json
simulator/simulator/config/bridge-demo-25.json
simulator/simulator/modbus_server.py
simulator/simulator/modbus_bridge.py
simulator/simulator/register_map.py
simulator/simulator/scheduler.py
simulator/simulator/spool.py
simulator/tests/check_h02_boundary.py
simulator/tests/test_cli_h03.py
simulator/tests/test_delivery_h03.py
simulator/tests/test_generation_h03.py
simulator/tests/test_modbus_h03.py
simulator/tests/test_replay_h03.py
simulator/tests/evidence/loopback-fc04.json
docs/hackathon_readiness/execution/H03_SIMULATOR_MODBUS_MQTT_BRIDGE.md
```

Build/egg-info/cache files are generated and ignored under simulator; installed
environments/wheels are temporary verification artifacts, not project outputs.

## Implementation and frozen interfaces

Envelope remains the approved additive `1.1.0`, with legacy `1.0.0` record
representation. Existing ML model/artifact versions and H00 hash/checkpoint
semantics did not change. Simulator package version remains `1.0.0`.

**Generation:** `next_record` and lazy `iter_records` generate one sample at a
time; finite `generate` retains its list API. Explicit seed/start/configuration
give byte-identical sequences. Each asset owns its RNG, injector, event clock,
thermal lag, energy and sequence. Final scenario V/I/PF determine P/S/equivalent
Q, then cumulative energy uses trapezoidal integration over actual positive
event seconds. First sample adds zero elapsed energy. Fictional thermal lag
uses elapsed seconds, tested under subdivision. Configured overload targets
130–140% of configured kVA rather than multiplying a low baseline. Voltage is
phase-neutral; configured rated LV voltage is line-line V, current is line A.
WTI is null/unavailable and labelled STATUS, never continuous °C. Standalone
fault copies are deep, preserving original provenance/hash bytes; generator
scenario processing owns energy history. Legacy standalone defaults are explicitly
fictional 500kVA/415V, not verified real transformer configuration.

**Replay:** canonical JSONL is portable, incremental, Decimal-preserving and
independent of missing raw files. Playback speed changes waiting only; source
event time is immutable. Separate registered destination/run lineage is required;
origin-equal IDs, mixed origins, changed duplicates, out-of-order input and source
hash mismatch reject. Destination preflight calls the actual registry/latest
APIs; an occupied live/different replay stream refuses. Same-run retry relies on
H02's immutable semantic identities. Historical HTTP replay does not mutate live
asset IDs, configuration or forward state. SQL-level state isolation is still
an infrastructure gate. Legacy/naive source replay requires an explicit timezone
assumption; field units remain UNKNOWN/UNVERIFIED. Raw CSV calls the unchanged
shared adapter loading, duplicate resolution, normalization, merge and validation
functions, including total power/counter fields and conflicting WTI→unknown;
there is no copied mapping implementation or Cartesian cross-file duplication.

**Modbus:** pinned **pymodbus==3.6.9**, APIs verified against installed source and
[matching official server documentation](https://pymodbus.readthedocs.io/en/v3.6.9/source/server.html).
The server uses `ModbusTcpServer`, zero-mode `ModbusSlaveContext`, an atomic input
datastore and a multi-unit `ModbusServerContext`. Only FC04 validates; other reads
and write requests are rejected. Default loopback `127.0.0.1:1502`; public binding
rejects. Wire/map version `fictional-lv-v1` is **a new fictional demo map**, not
an OEM address claim or a change to H00. It defines all 21 canonical measurements.
102 zero-based input registers use big-endian bytes/words, int32 values with
declared multipliers, uint64 counter at 1e-6kWh resolution, quality bitmap,
uint64 source epoch microseconds, uint32 sequence, unit/map/asset/scenario identity.
Protection contacts are read-only status values. Missing value = clear quality
bit + zero stored words; available zero = set bit. Counter decreases expose reset;
the bridge does not calculate a false delta. Counter/sequence overflow rejects.
No CT/PT conversion is applied to generated SI measurements; configuration and
units are explicitly fictional/SYNTHETIC. Header/body limits and conventions are
in [the map](../../../simulator/simulator/config/register-map-v1.json).

**Bridge:** FC04 sequence-before, two body blocks (100+2), sequence-after must
match. Bounded retries/backoff detect torn snapshots, timeout, invalid map/word/
asset/unit/quality/scaling, disconnect and reconnect. Last successful gateway
poll time and source event time remain separate. Missed sequences are counted;
backwards source sequence requires deliberate reinitialization/run recovery.
Existing MQTT topic `transformer/{id}/telemetry` receives canonical H00 provenance
and H01's exact semantic hash. Client IDs are unique, connection waits for
successful CONNACK, QoS1 publishes are non-retained and require PUBACK. Neither
transport nor `LIVE` labels establish verified source evidence. This supplied
map is for fictional simulated LV inputs; unknown historical units use canonical
HTTP replay, not guessed physical register values.

**Durability:** one process owns a locked, bounded local SQLite spool. SQLite is
delivery storage, not substitute PostgreSQL acceptance. FULL synchronous local
transactions persist semantic payloads, hashes, attempts, PUBACKs, quarantine,
retry deadlines and per-asset committed watermarks. Record/payload-byte limits and
physical page cap bound storage; quarantine consumes capacity. Reserved capacity
is checked before polling and acquisition pauses under backpressure; old records
are never silently evicted. A running source can advance during a pause; sequence
loss is visible, not guaranteed capture. An older pending/quarantined observation
blocks newer observations for its asset. Changed duplicates preserve the original
payload and quarantine with a counted conflict. Committed watermarks avoid
counting the same latest snapshot again after restart.

PUBACK never removes a row. The actual H02 read-only receipt route is used:
`GET /api/v1/ingestion/receipts/{snapshot_id}`. HTTP404 means not yet committed;
HTTP500, invalid/missing responses and connection errors retain/retry. A COMMITTED
receipt must match schema, snapshot/hash/accepted identity, asset/event time,
supported outcomes/availability and aware server timestamps before removal.
Conflict/mismatched accepted hash quarantines. Retry metadata never changes the
semantic payload; bounded exponential retry is local delivery metadata.

## Commands/configuration and actual results

Commands below used Python 3.13 in the isolated H03 environment at
`$env:TEMP/h03-simulator-verification/venv/Scripts/python.exe`, unless specified.
No H00 fixture suite, H01 regression/release/packaging suite or H02 migration suite
was rerun. The new boundary check only invokes the established H02 parser.

**PASSED**

- `python -m venv "$env:TEMP/h03-simulator-verification/venv"`: exit 0.
- Installed the approved existing H01 runtime wheel, pymodbus3.6.9 and source/test
  dependencies into that environment: exit 0. No fitted artifacts were fabricated.
- From `simulator/`, `python -m pip install -e '.[dev]'`: exit 0.
- `python -m pytest tests/test_schema.py -q`: exit 0, **19 passed**.
- Final combined focused command:

  ```text
  python -m pytest tests/test_schema.py tests/test_generation_h03.py tests/test_replay_h03.py tests/test_modbus_h03.py tests/test_delivery_h03.py tests/test_cli_h03.py -q
  ```

  exit 0, **57 passed in 19.46s**. Includes a real separate server process,
  independent FC04 client and bridge client, real disconnect/restart/reconnect,
  refused connection, map resolutions, signed Q, counter/reset/missing quality,
  deterministic lazy generation, elapsed thermal/energy, rated overload,
  replay time/lineage/unknowns, exact retries/conflict/quarantine, spool restart/
  ownership/capacity, receipt error behavior, independent 25-asset scheduling and
  stable CLI/help/legacy flags. Receipt/broker unit doubles are not SQL evidence.
- Narrow standalone check `python simulator/tests/check_h02_boundary.py`, using
  the actual H02 installed environment and installed H03 wheel: exit 0. Actual
  H02 MQTT parser accepts generated, decoded and replayed canonical envelopes
  with matching semantic hashes and rejects topic ID mismatch. No SQL or broker
  was contacted.
- `python -m simulator.cli --help` and `modbus-server --help`,
  `modbus-bridge --help`, `replay-canonical --help`: exit 0. Existing commands
  remain; required config/destination/run flags are present.
- `python -m pip check`: exit 0, no broken requirements.
- Focused `python -m ruff check simulator tests/test_generation_h03.py
  tests/test_replay_h03.py tests/test_modbus_h03.py tests/test_delivery_h03.py
  tests/test_cli_h03.py tests/check_h02_boundary.py --select F --output-format
  concise`: final exit 0, all checks passed.
- `python -m pip wheel . --no-deps --wheel-dir
  "$env:TEMP/h03-simulator-verification/wheels"`: exit 0. Packaged resources and
  final installed-wheel/import evidence are recorded in the final checks below.
- `python -m json.tool simulator/tests/evidence/loopback-fc04.json`: exit 0.

**FAILED then corrected**

- First new suite: exit 1, **30 passed, 1 failed**. The fake torn-snapshot test
  corrupted an incorrect read position. Second combined run: exit 1,
  **49 passed, 1 failed**; the fake assumed a one-block body. Corrected to the
  actual two-block body: four reads per attempt, eight for two exhausted retries.
  Targeted delivery/torn check then exit 0, **9 passed**; final 57-test run passed.
  No production assertion or test was deleted/relaxed.
- Initial focused Ruff check: exit 1, 18 unused import/local/f-string findings.
  Removed them only in H03 touched files; final static check exits 0.
- Temporary H02/H03 venv interpreter launchers became absent during verification;
  two attempted commands exited 1 before tests could start. Restored them with
  `python -m venv --upgrade <existing environment>` (installed dependencies
  retained), exit 0; CLI and actual H02 boundary checks then passed. No cause is
  inferred. An optional `rg` invocation used the wrong working-directory-relative
  backend path; resolved to the actual root path before the boundary check.

**SKIPPED / outside phase**

- No earlier phase suites, H07 scale/load rehearsal, frontend/display checks,
  deployment/root Compose work or H05 RUL/energy algorithm tests were run.
- 25-asset deterministic scheduling was unit-tested; 25 assets at five seconds
  for 30 minutes and p95 acquisition-to-display latency were not load-tested.

**BLOCKED infrastructure gates**

- `TEST_DATABASE_URL` and `MQTT_TEST_HOST` unset. No PostgreSQL CLI/server tools or
  Mosquitto executable were found on PATH. TCP checks: local1883 and8001 refused
  (Windows10061); local5432 accepted a connection. That listener is **not evidence
  of an approved disposable database**, credentials or CREATEDB permission, so
  it was not accessed. Docker server probe exited1: DockerDesktopLinuxEngine pipe
  absent. No production/operator database was used.
- Real broker CONNACK/PUBACK and broker stop/restart were not exercised. Broker
  failure/PUBACK distinction is covered only by focused delivery unit tests.
- Full bridge→MQTT consumer→SQL commit→matching receipt flow, source retry yielding
  one actual SQL row/side effect, database rollback, durable checkpoint recovery
  and receipt visibility after commit remain **BLOCKED on H02 infrastructure**.
- Replay registry/latest refusal and lineage were unit-tested against the actual
  shapes; real SQL live/replay state isolation remains blocked, not inferred.

## Real FC04 example

[Saved protocol evidence](../../../simulator/tests/evidence/loopback-fc04.json)
comes from an actual independent TCP client reading FC04 at loopback port64112,
unit1, address0, count102. The default repeatable demo configuration uses1502;
the test intentionally chose a free nonprivileged port. Source: fictional
`H03-SIM-01`, `2026-10-09T00:00:00Z`, sequence0, HEALTHY scenario. Test cadence was
3600s to hold a stable snapshot; configured demo cadence is5s.

```text
current_l1 = 12.28 A
zero-based address64, two signed int32 big-endian words, multiplier0.001A
encoded words [0,12280] → decoded current_l1 = 12.28A
source active_power_total = 7.67864787063kW → decoded = 7.679kW
timestamp registers4..7 = [6,23901,1928,40960] → 2026-10-09T00:00:00Z
winding_temperature = null; absent quality distinguishes it from a numeric zero
```

The decoder prepares the flat canonical body with source_name `fictional-modbus`,
acquisition source_kind/origin_kind SIMULATED, gateway `GW`, map_version
`fictional-lv-v1`, sequence0, declared synthetic units and source timestamp.
Its actual semantic snapshot/hash is:

```text
aae97bb922c7b2ac99dd5f1e50b41d2dbd2951837a902d0609e19cea63d1117b
```

This quantized decoded payload has its own deterministic semantic identity; it
does not reuse the unquantized generator hash. The saved full canonical payload
contains no raw CSV/VL12/VL23/VL31/server receipt fields. It is prepared for
`transformer/H03-SIM-01/telemetry`; publication/SQL receipt is **not** claimed.

## Compatibility limitations and remaining acceptance

- Raw adapter reuse needs the unchanged repository adapter or `--adapter-path`:
  the approved H01 wheel does not package `ml.adaptors`. Canonical JSONL removes
  this external/raw dependency; H01 packaging was not modified.
- Only the new fictional LV map is deployable. OEM maps, authorized LIVE inputs,
  verified historical units/timezones/ratios and replay-backed historical Modbus
  remain source-dependent/unimplemented; no plausible defaults stand in for them.
- The simulator server is not a durable historical recorder; restart with a fixed
  start regenerates its deterministic sequence. Use deliberate source run/start/
  destination selection after an established forward stream; backwards sequences
  and late/conflicting local records are visible rather than overwritten.
- One bridge owns a spool; one H02 runtime owns each asset. No horizontal delivery
  or ML-state consistency is claimed. Quarantine requires manual resolution.
- Real receipt/database integration must be completed once an approved disposable
  broker/backend/PostgreSQL environment is supplied. H02 acceptance remains
  blocked; H03's corresponding end-to-end acceptance is not yet met.
- New CLI errors propagate rather than reporting failed HTTP publication as
  successful; historical replay never silently invents UTC or physical units.

Actual commands and configuration details are in the
[H03 runbook](../../../simulator/H03_RUNBOOK.md). The exact next phase in the
roadmap is **H04 — frontend integration**, with the receipt gate carried forward
for eventual H06/H07 integration/rehearsal. H04/H05/H06/H07 were not started.

## Final artifact, link and preservation checks

- Final wheel build: exit0,
  `transformer_simulator-1.0.0-py3-none-any.whl`, actual SHA-256
  `743f9301333018c7e7a2c6c097f5429d66cb1e0f216d4dba4b4e4721e133a9f9`.
  Installed using `python -m pip install --no-deps --force-reinstall <wheel>` in
  H03 and H02 verification environments, exit0. Import from the temporary
  directory (outside the repository) resolved to `venv/Lib/site-packages/simulator`;
  server/bridge modules and packaged 102-register map loaded with pymodbus3.6.9,
  exit0, no repository-path injection. Rechecked the actual H02 parser against
  this final wheel with `python simulator/tests/check_h02_boundary.py`: exit0.
- Temporary focused verification helper
  `python "$env:TEMP/h03-simulator-verification/verify_artifacts.py"`: exit0.
  **96 pre-existing files checked, zero changed; exactly25 H03 paths, all within
  simulator or this new report**. Production ML/backend/frontend/Compose and
  H00/H01/H02 artifacts remain untouched.
- The helper actually invoked `python -m json.tool` on all **4** new JSON files,
  each exit0; saved decoded FC04 payload validates against the existing H00
  telemetry schema and matches H01's frozen semantic hash. This is a targeted
  H03 payload check, not a rerun of the H00 suite.
- **5** added local Markdown links resolve. `git diff --check -- simulator` exits0
  (Git notes future LF→CRLF normalization for two touched source files).

No blocked integration result is promoted by these package/unit checks. Stop for
manual team review; H04 is next, and H03/H02 SQL/broker acceptance remains blocked.
