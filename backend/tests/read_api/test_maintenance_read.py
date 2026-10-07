from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_maintenance_filters_and_window(read_client: TestClient, seeded: dict[str, Any]) -> None:
    path = f"/api/v1/transformers/{seeded['demo']}/maintenance"
    params = {"from": "2020-01-01T00:00:00Z", "to": "2020-01-01T01:00:00Z"}
    assert read_client.get(path, params=params).json()["total"] == 3
    done = read_client.get(path, params=params | {"status": "DONE"}).json()
    assert done["total"] == 1
    assert done["items"][0]["status"] == "DONE"
    assert done["items"][0]["timestamp"] == "2020-01-01T00:00:10Z"
    assert read_client.get(path, params=params | {"status": "bad"}).status_code == 422
    pages = [
        read_client.get(path, params=params | {"limit": 1, "offset": index}).json()["items"]
        for index in range(3)
    ]
    assert len({page[0]["id"] for page in pages}) == 3


def test_maintenance_timestamp_ties_page_by_id(
    read_client: TestClient, seeded: dict[str, Any], db: Session
) -> None:
    from app.models.maintenance_record import MaintenanceRecord
    from tests.read_api.conftest import BASE

    for _ in range(3):
        db.add(
            MaintenanceRecord(
                transformer_id=seeded["live"],
                timestamp=BASE,
                priority="NORMAL",
                recommendation="Routine monitoring",
                reason_codes=[],
            )
        )
    db.flush()
    path = f"/api/v1/transformers/{seeded['live']}/maintenance"
    params = {"from": "2020-01-01T00:00:00Z", "to": "2020-01-01T00:00:01Z", "limit": 1}
    pages = [
        read_client.get(path, params=params | {"offset": index}).json()["items"][0]
        for index in range(3)
    ]
    assert [row["id"] for row in pages] == sorted(row["id"] for row in pages)
    assert len({row["id"] for row in pages}) == 3
