# H00 validation evidence

Repository `develop`, baseline `29dcfaf5e12ef50446d1106c4994a721dc802476`;
initial working tree clean. No relevant production interface differences from
planning baseline `71c1b27200b91f3933c52692748935f4a62d63e8` in the narrow Git diff.

H00 artifacts and focused checks are ready for owner review. Review is pending;
no runtime integration is claimed. The user restricted all changes to the
contract and fixture/validation paths, so this report stays here rather than
the phase prompt's broader `docs/hackathon_readiness/execution/` suggestion.

See [the contract](../../../docs/contracts/hackathon-v1.1.md).

## Commands actually run and results

Environment: Windows PowerShell, Python 3.13.7, existing Pydantic 2.11.9;
temporary jsonschema 4.26.0 and pytest 8.4.2. Project dependencies were not changed.

| Command / check | Outcome |
|---|---|
| `git branch --show-current` | PASS, exit 0: develop |
| `git rev-parse HEAD` | PASS, exit 0: baseline SHA above |
| `git status --short` before editing | PASS, exit 0: empty |
| `rg --files -g AGENTS.md` | Exit 1: no matching instructions; parent-directory instruction checks also found none |
| `Get-Content` on all 11 requested specs and all 13 requested interfaces | PASS, exit 0; all paths existed; also read common types, query dependencies/resolution, API examples and dependency declarations |
| `git diff --name-only 71c1b27200b91f3933c52692748935f4a62d63e8 HEAD -- ml/pipeline backend/app/schemas backend/app/ml_client/base.py backend/app/api/v1 simulator/simulator/schema.py frontend/src/types.ts` | PASS, exit 0: no relevant interface delta |
| `python -m pip install --target "$env:TEMP\h00-jsonschema" jsonschema==4.26.0` | PASS, exit 0 |
| `python tests/fixtures/hackathon/validate.py` with temporary validator PYTHONPATH | PASS, exit 0: 15 JSON files, 10 schemas, 57 positive/negative examples, 13 arithmetic/eligibility cases, 10 ingestion/isolation traces, 3 hash vectors, bounded-query cases and 17 local Markdown links |
| `python -m json.tool <file>` | PASS, exit 0 for each of the 15 schema/fixture files; executed as subprocesses by validate.py; strict parsing additionally rejects nonfinite numbers/duplicate keys |
| Inline Python check using actual `TelemetryIn`, `MLResultIn`, `TransformerIn` | PASS, exit 0: legacy flat input/analytics/registry valid; true→integer 1 and null→null; actual backend rejected float/string protection, boolean measurement, naive time and raw/excluded fields |
| Independent PowerShell/.NET SHA-256 of each frozen canonical UTF-8 string | PASS, exit 0: all 3 digests match Python vectors |
| `python -m pip install --target "$env:TEMP\h00-pytest" pytest==8.4.2` | PASS, exit 0 |
| `python -m pytest backend/tests/test_telemetry_contract.py backend/tests/test_transformer_schemas.py backend/tests/test_analytics_schemas.py -q -p no:cacheprovider` with `PYTHONPATH="backend;$env:TEMP\h00-pytest"` | PASS, exit 0: 230 passed, no skips; 1 existing Starlette/httpx deprecation warning |
| Final Git scope, HEAD and whitespace checks | PASS: no tracked changes, only the 19 listed new H00 files; HEAD/branch unchanged; no commits/staging/push/merge |

Validation is reproducible using the commands in [README.md](README.md).
The backend compatibility check loaded the `legacy-flat-no-version`,
`existing-read-api-analytics-example`, and
`legacy-registry-nonpositive-remains-representable` examples, and rejected the
six named invalid examples through actual Pydantic models. No database fixture
or application service was invoked by the schema tests.

Independent digest check used `ConvertFrom-Json`, UTF8.GetBytes of
`canonical_utf8`, SHA256.Create().ComputeHash, and lowercase hexadecimal compared
to each stored `sha256`. Hash contexts containing received/retry metadata test
projection only; they cannot pass source-body validation.

## Failures, corrections, skipped and blocked checks

- Default sandbox process launch failed before executing each Git check:
  `helper_unknown_error: setup refresh had errors`, no exit statuses. The
  approved execution fallback ran them successfully; no final check depends on
  an unverified branch or filesystem assumption.
- Initial jsonschema import was missing. Initial pytest invocation exited 1
  (`No module named pytest`). Temporary installations resolved both; no final
  required validation dependency is blocked.
- One inline fixture-authoring command exceeded the Windows command-length
  limit (no execution), then the temporary helper generated the files. A later
  inline command exited 1 due to reserved Python identifier `as`; it performed
  no writes and was corrected. A patch-context mismatch and helper-delete tool
  failure were corrected; the temporary helper is absent from final outputs.
- The first check after formatting exited 1: formatting had changed the
  intentionally invalid protection token 1.0 into integer 1. The fixture was
  restored to 1.0 and the full validator passed. This demonstrates why input
  validation must precede numerical hash normalization. No failed validation is
  represented as a pass.
- SKIPPED by H00 scope: PostgreSQL/migrations/transaction rollback and restart,
  fitted ML release/empirical metrics, broker/Modbus, browser/DOM, Docker and
  portfolio soak. These are future H01–H07 gates, not H00 successes. No external
  infrastructure availability is inferred from schema regression passes.
- BLOCKED physical/empirical claims: original artifact release evidence,
  real-source unit/timezone/side/nameplate/authorization, life history, eligible
  hot-spot/insulation/loss parameters and real register encoding remain unknown.

## Exact final files (all newly created)

```text
docs/contracts/hackathon-v1.1.md
tests/fixtures/hackathon/README.md
tests/fixtures/hackathon/VALIDATION.md
tests/fixtures/hackathon/validate.py
tests/fixtures/hackathon/telemetry.schema.json
tests/fixtures/hackathon/asset.schema.json
tests/fixtures/hackathon/analytics.schema.json
tests/fixtures/hackathon/rul.schema.json
tests/fixtures/hackathon/energy.schema.json
tests/fixtures/hackathon/receipt.schema.json
tests/fixtures/hackathon/ingestion-outcome.schema.json
tests/fixtures/hackathon/checkpoint.schema.json
tests/fixtures/hackathon/register-map.schema.json
tests/fixtures/hackathon/latest.schema.json
tests/fixtures/hackathon/examples.json
tests/fixtures/hackathon/traces.json
tests/fixtures/hackathon/oracles.json
tests/fixtures/hackathon/hash-vectors.json
tests/fixtures/hackathon/query-cases.json
```

## Concrete examples and review gate

Synthetic D=.2, endpoint=1, rate=.01/hour under 100h horizon →
SIMULATED_ESTIMATE, rul_value=80, rul_unit=h. Rate bounds [.008,.012]/hour →
scenario range [66.6666666667,100] hours, not empirical confidence. Zero rate →
NO_CROSSING_WITHIN_HORIZON/null; a hypothetical real source missing prerequisites
→ INSUFFICIENT_DATA/null. No HI/anomaly-to-years formula exists here.

Supported synthetic 10kW samples at 00:00,01:00,02:00 UTC →20kWh under trapezoid;
0→10kW over 1h →5kWh. Counter 100→110 then reset→2 reports only 10kWh covered
energy, excludes the reset hour and leaves full-window consumed_kwh null.
Unknown units/long unsupported gaps produce no numeric total.

Remaining acceptance criterion: all four owners review the frozen interfaces.
Person 1 reviews artifact identity, readiness/RUL semantics and H01 state payload
compatibility; Person 2 reviews transaction/receipt/error/null/API storage;
Person 3 reviews integer contacts, null/source/unit/range display; Person 4 reviews
hash/source provenance and H03 register encoding/unit-ID mapping. Physical inputs
stay unknown, with explicit insufficient behavior rather than invented values.

Production application code, root contracts, unrelated documents, configuration,
database models, frontend, simulator and Compose remained untouched. H01 is the
next dependent phase. H00 stops here for review; H01–H07 were not begun.
