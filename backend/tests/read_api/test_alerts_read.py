from typing import Any

from fastapi.testclient import TestClient


def test_alert_filters_and_paging(read_client: TestClient, seeded: dict[str, Any]) -> None:
    path = f"/api/v1/transformers/{seeded['demo']}/alerts"
    params = {"from": "2020-01-01T00:00:00Z", "to": "2020-01-01T01:00:00Z"}
    all_rows = read_client.get(path, params=params).json()
    assert all_rows["total"] == 3
    critical = read_client.get(
        path, params=params | {"severity": "CRITICAL", "status": "OPEN"}
    ).json()
    assert critical["total"] == 1
    assert critical["items"][0]["severity"] == "CRITICAL"
    pages = [
        read_client.get(path, params=params | {"limit": 1, "offset": index}).json()["items"]
        for index in range(3)
    ]
    assert [page[0] for page in pages] == all_rows["items"]
    assert read_client.get(path, params=params | {"status": "bad"}).status_code == 422
