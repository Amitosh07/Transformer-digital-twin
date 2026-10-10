# H00 golden fixtures

Contract version 1.1.0. All demo assets and measurements are fictional. These
files freeze interfaces and arithmetic, not fitted-model performance.

Run from repository root:

```powershell
python tests/fixtures/hackathon/validate.py
```

Validation uses JSON Schema Draft 2020-12 (`jsonschema` with format checking).
`examples.json` assigns every example to a schema and expected validity. Negative
examples intentionally violate one rule. The validator also runs `python -m
json.tool` on every JSON file, checks semantic constraints, hash vectors,
arithmetic and local documentation links. It does not start production services.

See [the shared contract](../../../docs/contracts/hackathon-v1.1.md) and
[validation evidence](VALIDATION.md).

`traces.json` covers source/ingestion scenarios; `oracles.json` keeps arithmetic
independent of fitted behavior. `query-cases.json` freezes bounded energy queries.
`hash-vectors.json` contains canonical UTF-8 strings, expected SHA-256 and hash
contexts: server/retry metadata in those contexts tests exclusions and is **not**
a valid source POST body. The schemas and examples reject forged server fields.
Intentionally invalid examples can contain prohibited fields; valid canonical
examples contain none. Preserve the invalid protection token `1.0`: formatting
it as `1` changes the input type and invalidates that negative test.

No service is started and no database writes occur. For the environment used in
H00, missing validation packages were installed under the temporary directory:

```powershell
python -m pip install --target "$env:TEMP\h00-jsonschema" jsonschema==4.26.0
$env:PYTHONPATH = "$env:TEMP\h00-jsonschema"
$env:PYTHONDONTWRITEBYTECODE = '1'
python tests/fixtures/hackathon/validate.py
```
