from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_get_patch_and_duplicate(read_client: TestClient) -> None:
    asset = f"TX-create-{uuid4().hex[:8]}"
    response = read_client.post(
        "/api/v1/transformers",
        json={"id": asset, "name": "Asset", "rated_power_kva": 100, "oil_type": "type"},
    )
    assert response.status_code == 201
    assert response.json()["rated_current_a"] is None
    assert read_client.get(f"/api/v1/transformers/{asset}").json() == response.json()
    duplicate = read_client.post("/api/v1/transformers", json={"id": asset, "name": "Duplicate"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "HTTP_ERROR"
    patch = read_client.patch(f"/api/v1/transformers/{asset}", json={"rated_power_kva": None})
    assert patch.status_code == 200
    assert patch.json()["rated_power_kva"] is None
    assert patch.json()["oil_type"] == "type"
    assert patch.json()["name"] == "Asset"
    assert (
        read_client.patch(f"/api/v1/transformers/{asset}", json={"name": None}).status_code == 422
    )
    renamed = read_client.patch(f"/api/v1/transformers/{asset}", json={"name": "New name"})
    assert renamed.json()["name"] == "New name"
    assert read_client.patch(f"/api/v1/transformers/{asset}", json={}).status_code == 200


def test_transformer_paging(read_client: TestClient, seeded: dict) -> None:
    full = read_client.get("/api/v1/transformers", params={"limit": 5000}).json()
    first = read_client.get("/api/v1/transformers", params={"limit": 1}).json()
    second = read_client.get("/api/v1/transformers", params={"limit": 1, "offset": 1}).json()
    assert first["items"] + second["items"] == full["items"][:2]
    assert first["total"] == full["total"]
