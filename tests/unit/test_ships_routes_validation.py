import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.unit


def test_get_ship_with_malformed_uuid_returns_422():
    with TestClient(app) as client:
        response = client.get("/ships/not-a-valid-uuid")

    assert response.status_code == 422


def test_create_ship_missing_name_returns_422():
    with TestClient(app) as client:
        response = client.post("/ships", json={})

    assert response.status_code == 422


def test_openapi_documents_error_responses():
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()

    post_responses = spec["paths"]["/ships"]["post"]["responses"]
    assert "409" in post_responses

    get_one_responses = spec["paths"]["/ships/{ship_id}"]["get"]["responses"]
    assert "404" in get_one_responses
