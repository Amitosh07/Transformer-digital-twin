# Changelog

## Final backend phase — 2026-10-07

- Added deterministic canonical demo seeding through the existing batch service: healthy,
  stress, alarm/trip and recovery segments, null sensor dropout and nullable nameplate CLI options.
- Added transactional demo reset CLI and opt-in token-protected endpoint, both refusing production.
- Added Python 3.12 multi-stage non-root runtime image, DB wait/migrations entrypoint,
  persistent PostgreSQL/Mosquitto Compose services and a PowerShell demo runner.
- Added real captured API examples/reference, typed dashboard client, all-endpoint HTTP
  examples, team handoff, setup/troubleshooting and known limitations.
- Verified fresh-stack health/readiness, alert chain/recovery, MQTT ingress and reset/reseed
  count/hash determinism. Existing ingestion, alert and ML behavior/schema remain unchanged.

## Earlier backend phases

1. Canonical PostgreSQL database and Alembic migrations.
2. Strict Pydantic v2 schemas and shared error envelope.
3. Stub/Python/HTTP ML adapters and safe insufficient-result handling.
4. Single/batch/replay ingestion and quality statistics.
5. MQTT consumer, counters and graceful shutdown.
6. Dashboard read API, historical windows, SQL trends and demo metadata.
7. Alert lifecycle, maintenance dedupe and existing migration head 0003.
8. Profile-driven batch optimization, request correlation, readiness, compatibility and guards.
