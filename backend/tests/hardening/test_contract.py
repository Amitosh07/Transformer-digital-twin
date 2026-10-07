import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.main import create_app

SNAPSHOT = Path(__file__).resolve().parents[1] / "snapshots" / "openapi.json"


def field_paths(
    document: dict[str, Any],
    schema: dict[str, Any],
    prefix: str = "",
    visited: frozenset[str] = frozenset(),
) -> set[str]:
    reference = schema.get("$ref")
    if reference:
        if reference in visited:
            return set()
        target: Any = document
        for key in reference.removeprefix("#/").split("/"):
            target = target[key]
        return field_paths(document, target, prefix, visited | {reference})
    result = set()
    for name, value in schema.get("properties", {}).items():
        key = prefix + "." + name
        result.add(key)
        result.update(field_paths(document, value, key, visited))
    if "items" in schema:
        result.update(field_paths(document, schema["items"], prefix + "[]", visited))
    if isinstance(schema.get("additionalProperties"), dict):
        result.update(field_paths(document, schema["additionalProperties"], prefix + ".*", visited))
    for kind in ("anyOf", "allOf", "oneOf"):
        for value in schema.get(kind, []):
            result.update(field_paths(document, value, prefix, visited))
    return result


def assert_compatible(before: dict[str, Any], current: dict[str, Any]) -> None:
    for path, operations in before["paths"].items():
        assert path in current["paths"], f"Removed/renamed path: {path}"
        for method, operation in operations.items():
            if method not in ("get", "post", "patch", "put", "delete", "head", "options"):
                continue
            assert method in current["paths"][path], f"Removed method: {method} {path}"
            updated = current["paths"][path][method]
            old_parameters = {
                (item["in"], item["name"]) for item in operation.get("parameters", [])
            }
            parameters = {(item["in"], item["name"]) for item in updated.get("parameters", [])}
            assert old_parameters <= parameters, f"Removed/renamed parameter: {path}"
            for status, response in operation["responses"].items():
                assert status in updated["responses"], f"Removed response: {path} {status}"
                for mime, content in response.get("content", {}).items():
                    assert mime in updated["responses"][status].get("content", {})
                    old_fields = field_paths(before, content.get("schema", {}))
                    new_fields = field_paths(
                        current, updated["responses"][status]["content"][mime].get("schema", {})
                    )
                    assert old_fields <= new_fields, (
                        f"Removed/renamed response fields: {path}: {old_fields - new_fields}"
                    )


def test_openapi_snapshot_backward_compatibility() -> None:
    current = create_app().openapi()
    assert current["info"]["title"] == "Transformer Digital Twin API"
    assert current["info"]["description"]
    assert current["info"]["version"] == get_settings().schema_version
    assert current["info"]["contact"]["name"]
    assert_compatible(json.loads(SNAPSHOT.read_text(encoding="utf-8")), current)


@pytest.mark.parametrize("change", ["path", "parameter", "response_field"])
def test_contract_detects_breaking_changes(change: str) -> None:
    original = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    modified = copy.deepcopy(original)
    path = "/api/v1/transformers/{id}/latest"
    if change == "path":
        del modified["paths"][path]
    elif change == "parameter":
        modified["paths"][path]["get"]["parameters"] = []
    else:
        del modified["components"]["schemas"]["TelemetryOut"]["properties"]["oil_temperature"]
    with pytest.raises(AssertionError):
        assert_compatible(original, modified)


def test_contract_allows_additions() -> None:
    original = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    modified = copy.deepcopy(original)
    modified["paths"]["/extra"] = {}
    modified["components"]["schemas"]["TelemetryOut"]["properties"]["extra"] = {"type": "string"}
    assert_compatible(original, modified)
