from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.services.health import check_health


@pytest.mark.postgres
def test_health_real_postgres(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "schema_version": "1.0.0"}


def test_database_failure() -> None:
    session = Mock(spec=Session)
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private detail"))
    result = check_health(session, "1.0.0")
    assert result.model_dump() == {"status": "degraded", "db": "error", "schema_version": "1.0.0"}
