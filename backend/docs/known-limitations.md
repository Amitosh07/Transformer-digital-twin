# Known limitations

- MQTT queue is in memory. Paho acknowledges transport receipt before PostgreSQL commit;
  crash/overflow/failure can lose queued messages. The source must retain records for
  replay. Duplicate retries with identical asset/timestamp are safe. One worker processes
  queued messages and a stuck call cannot be forcibly cancelled after the shutdown budget.
- BackgroundTasks replay runs in the API process and is not durable. A restart can leave
  a RUNNING ingestion row; no durable job queue or automatic replay recovery is implemented.
- Stub ML scores are demonstration placeholders. They react to protection flags/presence,
  not rising thermal/current magnitudes. It implements no physical thermal twin. Thermal
  model outputs remain null. No actual Person-1 ML service/package was supplied for final
  acceptance; Python/HTTP adapters and their failure contracts are tested separately.
- Oil/thermal units remain unverified. The backend does no unit conversion/range checks
  on those values. Synthetic relative values do not establish sensor units. Nameplate
  ratings default null; loading cannot be calculated without supplied rated power.
- Lifecycle writers serialize on one transformer parent lock. Batch locks once per chunk;
  single/MQTT/replay lock per record. This preserves dedupe/order but limits simultaneous
  write throughput for one asset. No horizontal worker throughput guarantee is made.
- General API endpoints have no authentication/authorization. The optional demo reset
  alone has an admin token, is disabled by default and refuses ENV=production. Compose
  publishes localhost ports and uses local demo database credentials/anonymous MQTT.
- Reset deletes data globally across assets, retaining nameplate config unless requested.
  Pause MQTT/HTTP publishers and finish replays first; reset does not stop the consumer,
  cancel jobs or clear process counters. Identity sequences and creation timestamps are
  not reset, so determinism compares ordered telemetry values/counts rather than IDs.
- Offset pagination can shift during concurrent writes. Latest anchoring is required for
  older demo data. Alerts are filtered by first occurrence timestamp, not last_seen_at.
  Default 24h windows can omit earlier episodes; use explicit bounds within the 31-day cap.
- HTTP ML operation timeouts/retries are bounded per operation, not an overall deadline;
  Python entrypoints have no enforced execution timeout. Readiness checks reachability/
  importability without exercising prediction correctness, and MQTT connectivity is separate.
- Canonical field names and proxy alarm/trip interpretation remain fixed. A public-dataset
  proxy label cannot establish a physical equipment failure. Actual ML/twin integration,
  operational auth, durable transport/jobs and production deployment remain team work.
