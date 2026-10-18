#!/usr/bin/env python3
"""Exercise a running Shipyard instance end-to-end.

Used both for local verification after `docker compose up` and as a reusable
smoke-test step for CI or manual release verification. Exits non-zero on any
failure so it can gate a script or workflow.
"""

import argparse
import sys
import time

import httpx


def wait_for_ready(base_url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/ready", timeout=5)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def run_checks(base_url: str) -> list[str]:
    failures = []

    def check(name: str, condition: bool) -> None:
        print(f"[{'PASS' if condition else 'FAIL'}] {name}")
        if not condition:
            failures.append(name)

    health = httpx.get(f"{base_url}/health", timeout=5)
    check("GET /health returns 200", health.status_code == 200)

    ready = httpx.get(f"{base_url}/ready", timeout=5)
    check("GET /ready returns 200", ready.status_code == 200)

    version = httpx.get(f"{base_url}/version", timeout=5)
    check("GET /version returns 200", version.status_code == 200)
    check("GET /version includes version field", "version" in version.json())

    metrics = httpx.get(f"{base_url}/metrics", timeout=5)
    check("GET /metrics returns 200", metrics.status_code == 200)
    check("metrics expose http_requests_total", "http_requests_total" in metrics.text)

    ship_name = f"smoke-test-{int(time.time())}"
    created = httpx.post(f"{base_url}/ships", json={"name": ship_name}, timeout=5)
    check("POST /ships returns 201", created.status_code == 201)

    if created.status_code == 201:
        ship_id = created.json()["id"]

        fetched = httpx.get(f"{base_url}/ships/{ship_id}", timeout=5)
        check("GET /ships/{id} returns created ship", fetched.status_code == 200)

        updated = httpx.patch(f"{base_url}/ships/{ship_id}", json={"status": "launched"}, timeout=5)
        check("PATCH /ships/{id} updates status", updated.status_code == 200)

        deleted = httpx.delete(f"{base_url}/ships/{ship_id}", timeout=5)
        check("DELETE /ships/{id} returns 204", deleted.status_code == 204)

        missing = httpx.get(f"{base_url}/ships/{ship_id}", timeout=5)
        check("GET /ships/{id} returns 404 after delete", missing.status_code == 404)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=60.0, help="readiness timeout in seconds")
    args = parser.parse_args()

    print(f"waiting up to {args.timeout}s for {args.base_url}/ready ...")
    if not wait_for_ready(args.base_url, args.timeout):
        print("service did not become ready in time", file=sys.stderr)
        return 1

    failures = run_checks(args.base_url)
    if failures:
        print(f"\n{len(failures)} smoke check(s) failed: {failures}", file=sys.stderr)
        return 1

    print("\nall smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
