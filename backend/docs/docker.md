# Run the backend demo without make

Prerequisites: Docker Desktop with Linux containers, Docker Compose, and PowerShell.
Run from backend/. The Compose project is transformer-demo with simple service names
**db**, **mqtt**, **backend**, allowing Person 4 to merge it into the team stack.

## Exact PowerShell commands

```powershell
cd C:\Transformer-backend\backend
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
./scripts/demo.ps1 up
./scripts/demo.ps1 seed
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/health/ready
Invoke-RestMethod http://127.0.0.1:8001/api/v1/transformers/TX-001/latest
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers/TX-001/alerts?anchor=latest'
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/transformers/TX-001/maintenance?anchor=latest'
docker compose -f docker-compose.backend.yml logs --tail 100 -f backend mqtt
# Stop following logs with Ctrl+C.
./scripts/demo.ps1 reset -Yes
./scripts/demo.ps1 seed
./scripts/demo.ps1 down
```

Equivalent direct commands:

```powershell
docker compose -f docker-compose.backend.yml up --build -d --wait --wait-timeout 180
docker compose -f docker-compose.backend.yml exec -T backend python scripts/seed_demo.py
docker compose -f docker-compose.backend.yml exec -T backend python scripts/reset_demo.py --yes
docker compose -f docker-compose.backend.yml down
```

The runner creates .env from .env.example only if absent. up builds and waits for all
services to be healthy. down retains both named volumes; the next up retains data.
Reset deletes all telemetry, analytics, alerts, maintenance and ingestion runs in one
transaction, across every asset, retaining transformer configuration by default.
`./scripts/demo.ps1 reset -Yes -IncludeTransformers` deletes asset configuration too.
Reset requires explicit consent (-Yes / --yes) and always refuses ENV=production.
Stop publishers and finish replay jobs before resetting. MQTT process counters persist
through database reset and reset only on process restart.

## Ports, persistence and environment

| Host variable | Default port | Container destination |
| --- | ---: | --- |
| DEMO_HTTP_PORT | 8001 | backend:8000 |
| DEMO_DB_PORT | 55433 | db:5432 |
| DEMO_MQTT_PORT | 51885 | mqtt:1883 |

Host bindings are localhost only. Defaults avoid the existing development ports
8000,55432,51883. Edit .env to override host ports. The container always reaches db:5432
and mqtt:1883 regardless of host mappings. Local URLs in these examples need updating
when overriding DEMO_HTTP_PORT; verify_demo_stack.py also accepts --mqtt-port.

Named volumes transformer-demo_postgres_data and transformer-demo_mqtt_data hold
PostgreSQL data and Mosquitto persistence. These are separate from earlier dev containers.
The checked-in Mosquitto config is mounted read-only, enables local anonymous access and
persistent sessions/data. For team/network deployment configure appropriate broker access.
DEMO_DB_USER/PASSWORD/NAME configure this stack's database; the shipped credentials are
local demo defaults. Use URL-safe values in Compose's interpolated DATABASE_URL.
.env is loaded into backend; Compose explicitly sets DATABASE_URL to db, MQTT_ENABLED=true,
MQTT_HOST=mqtt, MQTT_PORT=1883, an independent client ID, and ML_BACKEND=stub. Override
these intentionally when integrating actual ML. Avoid multiple consumers with one client ID.

Shell entrypoint files are pinned to LF by backend/.gitattributes, including on Windows
checkouts. The multi-stage Python 3.12 slim image installs runtime wheels only. Its runtime user is
UID/GID 10001. It excludes .env, tests, caches and docs from the image/build context.
Entrypoint waits up to 60 seconds for SELECT 1, applies existing Alembic migrations, then
execs uvicorn so termination signals reach the server. Docker HEALTHCHECK calls /health;
use /health/ready for schema/ML readiness. Shutdown retains MQTT-before-HTTP-client ordering.

## Seed and HTTP reset options

```powershell
docker compose -f docker-compose.backend.yml exec -T backend python scripts/seed_demo.py --rows 2000 --transformer-id TX-001
docker compose -f docker-compose.backend.yml exec -T backend python scripts/seed_demo.py --reset --yes
# An explicitly supplied rating is optional configuration, never an inferred default:
# append --rated-power-kva <your-rating> or the other documented nameplate flags.
# --no-ml stores telemetry only; default demo verification requires stub ML.
```

For host-side HTTP seeding, install the backend dev environment first:

```powershell
.venv/Scripts/python.exe scripts/seed_demo.py --base-url http://127.0.0.1:8001
```

Optional HTTP reset is disabled by default (404). To use it, set DEMO_RESET_ENABLED=true
and a non-empty DEMO_ADMIN_TOKEN in .env, then recreate backend. Production still refuses.
Keep this token outside version control. The token protects only reset, not the read/write API.

```powershell
docker compose -f docker-compose.backend.yml up -d --force-recreate backend
# Also export the same token into this PowerShell session for the request header:
$env:DEMO_ADMIN_TOKEN = "<same token configured in .env>"
$demoAdminHeaders = @{ 'X-Admin-Token' = $env:DEMO_ADMIN_TOKEN }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/v1/admin/demo/reset -Headers $demoAdminHeaders
# The CLI HTTP mode reads DEMO_ADMIN_TOKEN from the environment or .env:
.venv/Scripts/python.exe scripts/reset_demo.py --base-url http://127.0.0.1:8001 --yes
```

Do not call the enabled reset during sample capture or while replay/publishers are active.
CLI in-container reset works without enabling the HTTP endpoint.

## Person 4: merge into the main Compose file

Copy db/mqtt/backend service definitions and the two named-volume declarations into the
team Compose file. Adjust backend build context to ./backend, env_file to ./backend/.env,
and the broker config bind path to ./backend/docker/mosquitto.conf. Remove this file's
project name when merging into the team's project. Retain dependency healthchecks and
container DNS names db/mqtt, or update DATABASE_URL/MQTT_HOST if renamed. A single
team database/broker may replace db/mqtt; preserve migrations, broker persistence and
unique MQTT_CLIENT_ID. Choose host ports once to avoid duplicate mappings. Backend API
inside the Compose network is http://backend:8000; host default is http://127.0.0.1:8001.

## Reproduce acceptance and capture samples

The verifier performs seed, duplicate HTTP seed, MQTT publish, reset, HTTP reseed,
count/hash comparisons and typed dashboard reads. It resets this demo stack's database.
Use it only after selecting this project's demo services and stopping other publishers.

```powershell
.venv/Scripts/python.exe scripts/verify_demo_stack.py
./scripts/demo.ps1 reset -Yes -IncludeTransformers
./scripts/demo.ps1 seed
.venv/Scripts/python.exe scripts/capture_samples.py --base-url http://127.0.0.1:8001
```

The default 2000-row seed starts 2026-01-01T00:00:00Z at 30-second intervals. Scenario
counts are 800/600/600. The fault segment has 240 alarm rows, 240 trip rows and 120 healthy
recovery rows. Ten healthy-segment sensor-dropout rows have oil_temperature=null.
With stub ML, healthy/stress scores are 90, alarm 55, trip 25 and recovery 90; thermal
magnitudes alone do not change stub scores. Eight alert episodes resolve during recovery,
and PLAN/URGENT maintenance remains open. Ratings remain null. Other ML backends and
custom alert settings can yield different analytical/lifecycle outcomes.
