# H06 local single-asset integration

The runtime uses the installed `transformer-ml-runtime` package and H01's
transactional adapter, with `ML_BACKEND=python`,
`ML_PYTHON_ENTRYPOINT=ml.pipeline:analyze`, and one backend worker. The checked
configuration explicitly selects `DEMO_UNVERIFIED_CONFIG`. It is not a fitted
release: operational risk/confidence remain unavailable. Authentic artifacts
are required to select `STRICT_FITTED`; see [artifact instructions](config/artifacts/README.md).

## Compose configuration

From the repository root, use these commands. They do not require a `.env`;
[the optional example](../.env.h06.example) documents overrides. Preserve an
existing `.env` and volumes. Never use `down -v` as setup.

```bash
docker compose config
docker compose up --build -d
docker compose ps
python simulator/scripts/demo_runtime.py setup
python simulator/scripts/demo_runtime.py primary
python simulator/scripts/demo_probe_modbus.py --asset H06-SIM-05 --unit 1
python simulator/scripts/demo_runtime.py check
python simulator/scripts/demo_oracles.py
python simulator/scripts/demo_runtime.py replay
```

`setup` requires the installed simulator/ML packages only in native mode;
Compose mode generates pre-roll inside the simulator container. The independent
host probe and arithmetic/replay helpers need the simulator and ML packages.
The shell wrappers call the same driver; `bash simulator/scripts/demo_setup.sh
--help` and equivalent primary/replay/check/25 wrappers are supported in Git Bash.
PowerShell should invoke the Python driver directly. `demo_25.sh` deliberately
refuses a scale run: the prepared configuration belongs to H07.

| Service | Loopback host port | Internal Compose address |
|---|---:|---|
| PostgreSQL 16 | 55433 | `db:5432` |
| Mosquitto 2 | 51885 | `mqtt:1883` |
| Backend | 8001 | `backend:8000` |
| React/Nginx | 5173 | `frontend:80` |
| Read-only Modbus | 1502 | `modbus-simulator:1502` |

The bridge is enabled by the `primary` profile after registration/pre-roll.
It polls every two seconds; the simulator's forward event cadence is five
seconds. Internal container binding is explicitly permitted in the server
configuration, with host publishing restricted to `127.0.0.1`. Native binding
remains loopback. Only FC04 is accepted. No real equipment controls are used.

Backend migrations execute on startup. DB/MQTT/backend/frontend readiness checks
and dependencies are configured. Named database and MQTT volumes are preserved;
the non-root bridge owns the bounded writable `/spool` volume. Backend installs
the real ML and backend wheels, with no host `site-packages` copying or repository
path hacks. The frontend's build-time API URL and CORS default to port 8001/5173.
Changing the frontend port also requires changing CORS explicitly.

The `.yaml` demo files contain JSON, which is valid YAML and is required by the
existing JSON-reading H03 CLI. Map `fictional-lv-v1` and `pymodbus==3.6.9` retain
their H03 address/quality/unit/byte/word-order contracts. The server uses unit 1
for the fictional asset `H06-SIM-05`. The one-hour historical pre-roll contains
60 explicitly declared 60-second observations, followed by five-second forward
records. The setup path uses the same register encoder/decoder, source,
gateway and register resolution as forward acquisition. Scenario gap tolerance
is explicitly 90 seconds; no ready flags or ML thresholds are forged.

These deterministic fixed-UTC scenario events are historical relative to wall
clock time. The dashboard correctly shows stale event time. API poll time and
MQTT connectivity do not change that event time. Restarting the deterministic
source against a populated asset may replay old identities; preserve existing
history and deliberately configure a separate asset/scenario for a new run.

## Native Windows path actually exercised

The clean-container gate failed on Docker Desktop storage I/O. A real native
fallback was exercised with PostgreSQL 18, AMQTT 0.11.3, the installed ML/simulator
wheels, Uvicorn, Vite, Edge and pymodbus 3.6.9. It proves the native services only,
not the Compose images or Mosquitto-specific deployment behavior.

The test PostgreSQL cluster was newly created for H06 and runs only on loopback
55433 as `h06_test`. Its final path is `D:\transformer-h06-disposable-20261009`.
Do not use an existing operator DB or an existing data directory. The following
commands describe the already-created disposable environment; they do not reset
or recreate it:

```powershell
& 'C:/Program Files/PostgreSQL/18/bin/pg_ctl.exe' -D 'D:/transformer-h06-disposable-20261009' -l 'D:/transformer-h06-postgres.log' -o '-h 127.0.0.1 -p 55433' -w start
$env:DATABASE_URL='postgresql+psycopg://h06_test@127.0.0.1:55433/h06_demo'
$env:ML_BACKEND='python'
$env:ML_PYTHON_ENTRYPOINT='ml.pipeline:analyze'
$env:ML_RUNTIME_MODE='DEMO_UNVERIFIED_CONFIG'
$env:ANALYTICS_POLICY_FILE=(Resolve-Path simulator/config/analytics-policy.json).Path
$env:MQTT_ENABLED='true'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='51885'
$env:CORS_ORIGINS='http://localhost:5173,http://127.0.0.1:5173'
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

In separate terminals, from the repository root unless noted:

```powershell
# Broker-only isolated installed dependencies; not an ML source-path workaround.
$env:PYTHONPATH="$env:TEMP/h06-broker-dependencies"
python simulator/scripts/native_broker.py

# Protocol/test dependencies were installed in a separate temporary target.
$env:PYTHONPATH="$env:TEMP/h06-test-dependencies"
python -m simulator.cli modbus-server --config simulator/config/hackathon-native-server.json
python simulator/scripts/demo_runtime.py setup --native
python simulator/scripts/demo_runtime.py primary --native
python simulator/scripts/demo_probe_modbus.py --asset H06-SIM-05 --unit 1
python simulator/scripts/demo_runtime.py check --native
python simulator/scripts/demo_oracles.py
python simulator/scripts/demo_runtime.py replay --native

# Frontend terminal, from frontend/:
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

The temporary dependencies were installed using:

```powershell
python -m pip install --target "$env:TEMP/h06-test-dependencies" 'pytest>=8,<10' 'pymodbus==3.6.9' 'paho-mqtt>=2,<3'
python -m pip install --target "$env:TEMP/h06-broker-dependencies" 'amqtt==0.11.3'
```

The native ML package was installed from the approved H05 runtime wheel; the
simulator was installed from a narrow temporary package export using `pip
install --no-deps --no-build-isolation`. Both import from installed packages
when run outside the repository root. For a new machine, build/install these
repository packages with their declared dependencies; temporary wheel paths
from this execution are evidence, not a required developer-specific dependency.

## Resources, receipts and evidence

Actual implemented resources:

```text
GET /api/v1/transformers/H06-SIM-05/latest
GET /api/v1/transformers/H06-SIM-05/rul
GET /api/v1/transformers/H06-SIM-05/rul/projection
GET /api/v1/transformers/H06-SIM-05/energy?window=1h&anchor=latest
GET /api/v1/ingestion/receipts/{snapshot_id}
```

RUL reads accepted persisted analytics. Projection is a separate additive
resource reading the matching checkpoint curve; the frozen H00 RUL shape is
unchanged. Energy calls H05 with bounded persisted telemetry and explicit
per-asset source policies. It honors existing `from`, `to`, `anchor=latest|now`
and `window=1h|6h|24h|7d` semantics. The UI's two-hour choice sends explicit
`from`/`to`, not an unsupported `window=2h`. Boundary interpolation is explicitly
permitted only for the declared fictional instantaneous-power policy; excessive
gaps, unknown units and counter resets remain excluded/visible.

`demo_oracles.py` submits separate clearly fictional arithmetic observations
to the real backend: `H06-RUL-ORACLE` gives 80 hours; constant 10 kW over two
hours gives 20 kWh; a one-hour 0→10 kW ramp gives 5 kWh; counter reset yields
13 covered kWh and null whole-window energy. An explicitly unverified validation
input remains null for operational life/risk/loss/efficiency. These arithmetic
HTTP cases supplement the primary Modbus trace; they do not replace FC04 proof.

Replay uses registered `H06-REPLAY-R1`, run `H06-R1`, preserved original event
times and simulated origin lineage. It is a visible **REPLAYED HTTP fallback**,
not LIVE telemetry or proof of Modbus transport.

PUBACK increments broker acknowledgment only. Spool removal requires a matching
committed receipt/hash. Missing receipts, 500s and connection failures retain
records. Conflicts are quarantined. Capacity is 10,000 records/16 MiB semantic
payload with backpressure, not silent deletion; quarantine consumes capacity.
The native spool is ignored at `config/.h06-native-spool/`. Stop only services
started for this demo; preserve the spool and all existing database volumes.
After restarting PostgreSQL, restart the single backend process to reacquire
its PostgreSQL advisory runtime lease before enabling additional ingestion.
The deployment supports one ML worker only; it does not synchronize independent
workers or claim automatic lease recovery after a database restart.

[H06 execution report](../docs/hackathon_readiness/execution/H06_RUNTIME_AND_SINGLE_ASSET_INTEGRATION.md)
records native SQL, broker, Modbus, actual browser and outage evidence and the
unmet Docker gate. H07 scale/soak was not performed.
