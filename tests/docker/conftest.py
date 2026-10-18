import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_docker():
    if not _docker_available():
        pytest.skip("Docker daemon is not available in this environment")
