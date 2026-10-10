from typing import Any

from fastapi.testclient import TestClient


def test_distinct_scenarios(read_client: TestClient, seeded: dict[str, Any]) -> None:
    result = read_client.get("/api/v1/scenarios", params={"limit": 5000}).json()
    scenario = next(row for row in result["items"] if row["scenario_id"] == "read-scenario")
    assert scenario["row_count"] == 4
    assert scenario["first_timestamp"] == "2020-01-01T00:00:00Z"
    assert scenario["last_timestamp"] == "2020-01-01T00:00:30Z"
    first = read_client.get("/api/v1/scenarios", params={"limit": 1}).json()
    second = read_client.get("/api/v1/scenarios", params={"limit": 1, "offset": 1}).json()
    assert first["items"] + second["items"] == result["items"][:2]
