import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.unit


def test_health_reports_ok():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_configured_version():
    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert "git_sha" in body


def test_metrics_endpoint_exposes_prometheus_format():
    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text
    assert "app_info" in response.text


def test_unknown_route_returns_404():
    with TestClient(app) as client:
        response = client.get("/does-not-exist")

    assert response.status_code == 404
