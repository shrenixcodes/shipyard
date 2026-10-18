import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

pytestmark = pytest.mark.integration


def test_ready_reports_ok_when_database_is_reachable(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_ready_reports_503_when_database_is_unreachable():
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://shipyard:shipyard@127.0.0.1:1/shipyard"
    get_settings.cache_clear()

    try:
        with TestClient(app) as broken_client:
            response = broken_client.get("/ready")
    finally:
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_metrics_reflect_database_readiness_gauge(client):
    client.get("/ready")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "app_database_up" in response.text
