import pytest

pytestmark = pytest.mark.integration


def test_create_and_get_ship(client):
    response = client.post("/ships", json={"name": "Discovery"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Discovery"
    assert body["status"] == "keel_laid"

    get_response = client.get(f"/ships/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_create_ship_with_duplicate_name_returns_409(client):
    client.post("/ships", json={"name": "Enterprise"})
    response = client.post("/ships", json={"name": "Enterprise"})

    assert response.status_code == 409


def test_create_ship_with_invalid_payload_returns_422(client):
    response = client.post("/ships", json={"name": ""})
    assert response.status_code == 422


def test_create_ship_treats_whitespace_padded_duplicate_as_conflict(client):
    client.post("/ships", json={"name": "Nebuchadnezzar"})
    response = client.post("/ships", json={"name": "  Nebuchadnezzar  "})

    assert response.status_code == 409


def test_list_ships_returns_created_ships(client):
    client.post("/ships", json={"name": "Voyager"})
    client.post("/ships", json={"name": "Defiant"})

    response = client.get("/ships")

    assert response.status_code == 200
    names = {ship["name"] for ship in response.json()}
    assert {"Voyager", "Defiant"}.issubset(names)


def test_get_missing_ship_returns_404(client):
    response = client.get("/ships/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_ship_status(client):
    created = client.post("/ships", json={"name": "Normandy"}).json()

    response = client.patch(f"/ships/{created['id']}", json={"status": "launched"})

    assert response.status_code == 200
    assert response.json()["status"] == "launched"


def test_update_missing_ship_returns_404(client):
    response = client.patch(
        "/ships/00000000-0000-0000-0000-000000000000", json={"status": "launched"}
    )
    assert response.status_code == 404


def test_delete_ship_removes_it(client):
    created = client.post("/ships", json={"name": "Nostromo"}).json()

    delete_response = client.delete(f"/ships/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/ships/{created['id']}")
    assert get_response.status_code == 404


def test_delete_missing_ship_returns_404(client):
    response = client.delete("/ships/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
