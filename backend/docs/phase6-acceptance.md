# Phase 6 acceptance results

Verified on feature/backend-api on 2026-10-07. All changes are inside backend/.
CONTEXT.md, ingestion.md and mqtt.md were read before implementation.

## Checks

| Check | Result |
| --- | --- |
| Full pytest on real PostgreSQL and Mosquitto | PASS, 557 tests, no skips, 137.82 seconds |
| New read-API coverage | PASS, 71 tests |
| Earlier regression coverage | PASS, 486 tests |
| Ruff check | PASS |
| Ruff format --check | PASS |
| EXPLAIN on 20,000 telemetry rows | PASS, natural Bitmap Index Scan |
| Migration downgrade/upgrade/check | PASS, no schema drift |
| Canonical-name scan of new files and OpenAPI | PASS |
| Single telemetry write path | PASS, still ingestion_service.ingest_record |
| git diff --check | PASS |

The existing Starlette/httpx TestClient deprecation remains (one warning).
The Phase 2 ORM schema test now includes and checks the additive data_source field.

## Endpoint and contract coverage

- Seed two transformers through ingest_record with stub ML: healthy, protection-alarm
  stress, protection-trip proxy and insufficient-data rows. Every endpoint group returns
  its typed public shape; window reads isolate the requested transformer.
- Transformer list/create/get/patch: ID ordering, bounded pages, 409 duplicate, optional
  nameplate nulls, explicit-null clearing, omitted values retained, empty patches and
  null-name rejection. Unknown assets return the standard 404 error on every asset route.
- Latest: empty assets return 200/null readings; newest telemetry receives only its own
  analytics; versions, source/scenario metadata, true/false demo cases and all-time OPEN
  alert counts are correct. Unexpected stored error_detail text is replaced with the short
  Phase 3 failure message; historical analytics are never attached to a newer unanalysed row.
- History: current defaults, configured default window, inclusive bounds, from>=to errors,
  maximum-window errors, naive timestamp rejection, offset normalization, page caps,
  configurable limits, zero offset, non-overlapping complete paging and descending order.
  All history groups share the same window validation. anchor=latest finds old demo rows.
- Projection: only selected allowed fields plus timestamp; null remains null and zero stays
  zero. Excluded variants, raw/unknown names, empty selections and unselectable metadata
  return 422 with the allowlist. Health/analytics retain insufficient rows with null outputs.
- Alert/maintenance filters, deterministic paging and maintenance timestamp ties by ID.
- Scenarios: distinct non-null metadata, first/last time and row count, sorted bounded paging.
- Trends: hand-computed mean/min/max/count for telemetry and proxy analytic signals;
  empty/all-null gaps remain null, zeros count, no-data signals are named, and protection
  events are listed separately. All four preset widths, latest anchoring, maximum 8 signals,
  rejected unknown/protection signals, extended explicit-window bucket bounds and 500-event
  cap are covered. Aggregation runs in PostgreSQL date_bin.
- Demo rule unit tests: non-null scenario metadata or configured case-insensitive source
  prefix; replay-public-data and other configured demo sources count, ordinary plant data
  does not. Configured prefix overrides and empty scenario metadata are covered.
- CORS preflight succeeds for the default localhost Streamlit origin; credentials stay false.
  Comma-separated origins and legacy JSON-array values are accepted.
- OpenAPI includes all 12 new operations, response models, examples, tags, proxy-risk
  descriptions and shared ErrorResponse schemas. No excluded/raw field names are present.

## Index and migration evidence

The seeded 20,000-row planner fixture ANALYZEs telemetry and EXPLAINs the production
telemetry window statement for a selective one-minute range. The final plan was:

```text
Limit -> Sort(timestamp, id) -> Bitmap Heap Scan
  -> Bitmap Index Scan: ix_telemetry_transformer_timestamp_desc
```

The index condition constrained transformer_id and both timestamp bounds. No
`enable_seqscan=off` was used. Maintenance index presence is also asserted.
The planner fixture uses SQL bulk-loading only for its synthetic planner dataset;
application telemetry writes remain exclusively through ingest_record.

Migration 0002 adds ix_maintenance_records_transformer_timestamp_desc. Maintenance was
previously the only time-series table without a transformer/timestamp index. This necessity
was explained before creating the migration. No columns or canonical schema changed.
The full suite upgrades, downgrades to base, upgrades again and runs Alembic schema checks
against disposable PostgreSQL. The local development database was also upgraded to 0002
and checked after the final suite.

## Existing 10,000-row regression benchmark

| Operation | Seconds | Inserted | Duplicates | Parse errors | Range errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial stub batch | 70.696 | 10000 | 0 | 0 | 0 |
| Duplicate batch | 47.535 | 0 | 10000 | 0 | 0 |

This is the unchanged Phase 4 benchmark; timings reflect this local Docker run.

## Reproduction and files

The tests use Python 3.12, real PostgreSQL 16 at localhost:55432 and the existing Docker
Mosquitto broker at localhost:51883. Fixtures create, migrate and drop disposable databases.
Both TEST_DATABASE_URL and MQTT_TEST_HOST were set, so there were no skipped tests.
See read-api-notes.md for parameters, defaults, limits, bucket widths, demo semantics,
anchor=latest, migration commands and exact test commands.

See FILES.md, Phase 6 files, for the exact 29 created and 12 changed files.
