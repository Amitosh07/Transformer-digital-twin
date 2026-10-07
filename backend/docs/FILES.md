# Files created for Phase 1

- `backend/.env.example`
- `backend/.gitignore`
- `backend/README.md`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_initial_canonical_telemetry_database.py`
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/api/v1/__init__.py`
- `backend/app/api/v1/health.py`
- `backend/app/api/v1/router.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/core/errors.py`
- `backend/app/core/logging.py`
- `backend/app/db/__init__.py`
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/app/ml_client/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/models/alert.py`
- `backend/app/models/analytics.py`
- `backend/app/models/ingestion_run.py`
- `backend/app/models/maintenance_record.py`
- `backend/app/models/telemetry.py`
- `backend/app/models/transformer.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/health.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/health.py`
- `backend/app/schemas/telemetry.py`
- `backend/app/services/__init__.py`
- `backend/app/services/health.py`
- `backend/docs/CONTEXT.md`
- `backend/docs/FILES.md`
- `backend/pyproject.toml`
- `backend/tests/conftest.py`
- `backend/tests/test_config.py`
- `backend/tests/test_errors.py`
- `backend/tests/test_health.py`
- `backend/tests/test_main.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_models.py`
- `backend/tests/test_schemas.py`
- `backend/tests/test_session.py`

# Phase 2 files

Created:

- `backend/app/schemas/alert.py`
- `backend/app/schemas/analytics.py`
- `backend/app/schemas/common.py`
- `backend/app/schemas/fields.py`
- `backend/app/schemas/maintenance.py`
- `backend/app/schemas/quality.py`
- `backend/app/schemas/state.py`
- `backend/app/schemas/transformer.py`
- `backend/tests/test_analytics_schemas.py`
- `backend/tests/test_common_schemas.py`
- `backend/tests/test_quality.py`
- `backend/tests/test_schema_orm.py`
- `backend/tests/test_telemetry_contract.py`
- `backend/tests/test_transformer_schemas.py`

Changed:

- `backend/.env.example`
- `backend/README.md`
- `backend/app/core/config.py`
- `backend/app/core/errors.py`
- `backend/app/schemas/telemetry.py`
- `backend/docs/FILES.md`
- `backend/tests/test_config.py`
- `backend/tests/test_errors.py`

# Phase 3 files

Created:

- `backend/app/ml_client/base.py`
- `backend/app/ml_client/stub_client.py`
- `backend/app/ml_client/python_client.py`
- `backend/app/ml_client/http_client.py`
- `backend/app/ml_client/safe.py`
- `backend/app/ml_client/factory.py`
- `backend/tests/ml_client/__init__.py`
- `backend/tests/ml_client/conftest.py`
- `backend/tests/ml_client/test_base.py`
- `backend/tests/ml_client/test_stub_client.py`
- `backend/tests/ml_client/test_python_client.py`
- `backend/tests/ml_client/test_http_client.py`
- `backend/tests/ml_client/test_safe.py`
- `backend/tests/ml_client/test_factory.py`
- `backend/docs/ml-integration-notes.md`

Changed:

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/pyproject.toml`
- `backend/tests/test_config.py`
- `backend/README.md`
- `backend/docs/FILES.md`

# Phase 4 files

Created:

- `backend/app/api/v1/simulate.py`
- `backend/app/api/v1/telemetry.py`
- `backend/app/repositories/analytics_repo.py`
- `backend/app/repositories/ingestion_run_repo.py`
- `backend/app/repositories/telemetry_repo.py`
- `backend/app/repositories/transformer_repo.py`
- `backend/app/schemas/ingestion.py`
- `backend/app/services/hooks.py`
- `backend/app/services/ingestion_service.py`
- `backend/app/services/quality_stats.py`
- `backend/app/services/replay_service.py`
- `backend/docs/ingestion.md`
- `backend/docs/phase4-acceptance.md`
- `backend/tests/ingestion/__init__.py`
- `backend/tests/ingestion/conftest.py`
- `backend/tests/ingestion/test_batch.py`
- `backend/tests/ingestion/test_concurrency.py`
- `backend/tests/ingestion/test_lifespan.py`
- `backend/tests/ingestion/test_logging.py`
- `backend/tests/ingestion/test_performance.py`
- `backend/tests/ingestion/test_quality_stats.py`
- `backend/tests/ingestion/test_replay.py`
- `backend/tests/ingestion/test_single.py`

Changed:

- `backend/README.md`
- `backend/alembic/env.py`
- `backend/app/api/v1/router.py`
- `backend/app/main.py`
- `backend/app/ml_client/factory.py`
- `backend/docs/FILES.md`
- `backend/docs/ml-integration-notes.md`

# Phase 5 files

Created:

- `backend/app/api/v1/mqtt_status.py`
- `backend/app/mqtt/__init__.py`
- `backend/app/mqtt/consumer.py`
- `backend/app/mqtt/message_handler.py`
- `backend/app/schemas/mqtt.py`
- `backend/app/services/mqtt_status_service.py`
- `backend/docs/mqtt.md`
- `backend/docs/phase5-acceptance.md`
- `backend/tests/mqtt/__init__.py`
- `backend/tests/mqtt/conftest.py`
- `backend/tests/mqtt/mosquitto.conf`
- `backend/tests/mqtt/test_broker.py`
- `backend/tests/mqtt/test_config.py`
- `backend/tests/mqtt/test_consumer.py`
- `backend/tests/mqtt/test_lifespan.py`
- `backend/tests/mqtt/test_message_handler.py`
- `backend/tests/mqtt/test_mqtt_status.py`
- `backend/tests/mqtt/test_mqtt_status_service.py`

Changed:

- `backend/.env.example`
- `backend/README.md`
- `backend/app/api/v1/router.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/docs/FILES.md`
- `backend/docs/ingestion.md`
- `backend/pyproject.toml`

# Phase 6 files

Created:

- `backend/alembic/versions/0002_maintenance_window_index.py`
- `backend/app/api/v1/alerts_read.py`
- `backend/app/api/v1/history.py`
- `backend/app/api/v1/latest.py`
- `backend/app/api/v1/maintenance_read.py`
- `backend/app/api/v1/query_dependencies.py`
- `backend/app/api/v1/read_examples.py`
- `backend/app/api/v1/transformers.py`
- `backend/app/repositories/alert_repo.py`
- `backend/app/repositories/maintenance_repo.py`
- `backend/app/repositories/query_helpers.py`
- `backend/app/schemas/query.py`
- `backend/app/services/demo_mode.py`
- `backend/app/services/query_service.py`
- `backend/app/services/trend_service.py`
- `backend/docs/phase6-acceptance.md`
- `backend/docs/read-api-notes.md`
- `backend/tests/read_api/__init__.py`
- `backend/tests/read_api/conftest.py`
- `backend/tests/read_api/test_alerts_read.py`
- `backend/tests/read_api/test_contract.py`
- `backend/tests/read_api/test_demo_mode.py`
- `backend/tests/read_api/test_history.py`
- `backend/tests/read_api/test_index.py`
- `backend/tests/read_api/test_latest.py`
- `backend/tests/read_api/test_maintenance_read.py`
- `backend/tests/read_api/test_scenarios.py`
- `backend/tests/read_api/test_transformers.py`
- `backend/tests/read_api/test_trends.py`

Changed:

- `backend/.env.example`
- `backend/README.md`
- `backend/app/api/v1/router.py`
- `backend/app/core/config.py`
- `backend/app/models/maintenance_record.py`
- `backend/app/repositories/analytics_repo.py`
- `backend/app/repositories/telemetry_repo.py`
- `backend/app/repositories/transformer_repo.py`
- `backend/app/schemas/state.py`
- `backend/docs/FILES.md`
- `backend/pyproject.toml`
- `backend/tests/test_schema_orm.py`

# Phase 7 files

Created:

- `backend/alembic/versions/0003_alert_lifecycle.py`
- `backend/app/api/v1/alerts_write.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/maintenance_service.py`
- `backend/docs/alerts.md`
- `backend/docs/phase7-acceptance.md`
- `backend/tests/alerts/__init__.py`
- `backend/tests/alerts/conftest.py`
- `backend/tests/alerts/test_concurrency.py`
- `backend/tests/alerts/test_contract.py`
- `backend/tests/alerts/test_endpoints.py`
- `backend/tests/alerts/test_lifecycle.py`
- `backend/tests/alerts/test_rules.py`
- `backend/tests/alerts/test_scenario.py`

Changed:

- `backend/.env.example`
- `backend/README.md`
- `backend/app/api/v1/read_examples.py`
- `backend/app/api/v1/router.py`
- `backend/app/core/config.py`
- `backend/app/models/alert.py`
- `backend/app/repositories/alert_repo.py`
- `backend/app/repositories/maintenance_repo.py`
- `backend/app/repositories/transformer_repo.py`
- `backend/app/schemas/alert.py`
- `backend/app/schemas/maintenance.py`
- `backend/app/services/hooks.py`
- `backend/app/services/ingestion_service.py`
- `backend/docs/FILES.md`
- `backend/docs/ingestion.md`
- `backend/docs/read-api-notes.md`
- `backend/tests/read_api/conftest.py`


# Phase 8 files

Created:

- `backend/app/core/request_logging.py`
- `backend/app/repositories/readiness_repo.py`
- `backend/app/schemas/readiness.py`
- `backend/app/services/batch_ingestion.py`
- `backend/app/services/readiness_service.py`
- `backend/docs/hardening.md`
- `backend/docs/performance.md`
- `backend/docs/phase8-acceptance.md`
- `backend/docs/profile-after-first.json`
- `backend/docs/profile-after.json`
- `backend/docs/profile-before.json`
- `backend/docs/profile-final.json`
- `backend/scripts/check_coverage.py`
- `backend/scripts/profile_ingest.py`
- `backend/scripts/snapshot_openapi.py`
- `backend/tests/hardening/__init__.py`
- `backend/tests/hardening/conftest.py`
- `backend/tests/hardening/test_concurrency.py`
- `backend/tests/hardening/test_contract.py`
- `backend/tests/hardening/test_guards.py`
- `backend/tests/hardening/test_readiness.py`
- `backend/tests/hardening/test_repository_recovery.py`
- `backend/tests/hardening/test_requests.py`
- `backend/tests/performance/__init__.py`
- `backend/tests/performance/conftest.py`
- `backend/tests/performance/test_differential.py`
- `backend/tests/performance/test_million_reads.py`
- `backend/tests/snapshots/openapi.json`

Changed:

- `backend/README.md`
- `backend/app/api/v1/health.py`
- `backend/app/core/errors.py`
- `backend/app/main.py`
- `backend/app/ml_client/http_client.py`
- `backend/app/ml_client/python_client.py`
- `backend/app/repositories/alert_repo.py`
- `backend/app/repositories/analytics_repo.py`
- `backend/app/repositories/maintenance_repo.py`
- `backend/app/repositories/telemetry_repo.py`
- `backend/app/repositories/transformer_repo.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/ingestion_service.py`
- `backend/docs/FILES.md`
- `backend/docs/alerts.md`
- `backend/docs/ingestion.md`
- `backend/pyproject.toml`
