"""Container-level smoke and persistence tests.

These exercise the real built image and a real PostgreSQL container via
docker compose. They are slow and require a working Docker daemon, so they
are excluded from the default `pytest` run and from CI's fast unit/integration
jobs; run them explicitly with `pytest -m docker`.
"""

import subprocess
import time

import httpx
import pytest

pytestmark = pytest.mark.docker

BASE_URL = "http://localhost:8000"
COMPOSE_SERVICES = ["db", "app"]


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], capture_output=True, text=True, check=False)


def _wait_ready(timeout: float = 90.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{BASE_URL}/ready", timeout=3).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


@pytest.fixture(scope="module")
def running_stack():
    up = _compose("up", "-d", "--build", *COMPOSE_SERVICES)
    assert up.returncode == 0, f"docker compose up failed:\n{up.stderr}"

    assert _wait_ready(), "application did not become ready in time"

    yield

    _compose("down", "-v")


def test_health_and_ready_respond(running_stack):
    health = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert health.status_code == 200

    ready = httpx.get(f"{BASE_URL}/ready", timeout=5)
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"


def test_container_runs_as_non_root_user(running_stack):
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "app", "whoami"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "shipyard"


def test_graceful_shutdown_completes_quickly(running_stack):
    start = time.monotonic()
    stop = _compose("stop", "-t", "15", "app")
    elapsed = time.monotonic() - start

    assert stop.returncode == 0
    assert elapsed < 20, "container did not shut down gracefully within its stop timeout"

    restart = _compose("start", "app")
    assert restart.returncode == 0
    assert _wait_ready(), "application did not become ready again after restart"


def test_postgres_data_persists_across_db_restart(running_stack):
    created = httpx.post(f"{BASE_URL}/ships", json={"name": "persistence-check"}, timeout=5)
    assert created.status_code == 201
    ship_id = created.json()["id"]

    restart_db = _compose("restart", "db")
    assert restart_db.returncode == 0

    assert _wait_ready(), "application did not reconnect after database restart"

    fetched = httpx.get(f"{BASE_URL}/ships/{ship_id}", timeout=5)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "persistence-check"
