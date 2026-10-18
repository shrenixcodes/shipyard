# Shipyard

Shipyard is a small FastAPI service used to demonstrate a complete, production-oriented
DevOps workflow: a containerized API backed by PostgreSQL, automated tests, CI/CD with
image scanning and GHCR publishing, scripted deployment with automatic rollback, and a
Prometheus/Grafana monitoring stack.

The domain itself is intentionally simple — a CRUD API for tracking `ships` (name, status,
timestamps) moving through a build lifecycle (`keel_laid` → `under_construction` →
`launched` → `commissioned` → `decommissioned`) — so that the DevOps machinery around it is
the point, not the business logic.

## Capabilities

- FastAPI application with async SQLAlchemy/PostgreSQL persistence and Alembic migrations.
- `/health`, `/ready`, `/version`, and `/metrics` (Prometheus) endpoints with a real
  liveness/readiness distinction.
- Structured JSON logging.
- Unit, integration (real PostgreSQL), and container-level smoke tests.
- Multi-stage, non-root Dockerfile and a docker-compose stack (app, PostgreSQL, Prometheus,
  Grafana) with healthchecks, persistent volumes, and resource limits.
- GitHub Actions CI (lint, unit tests, integration tests, dependency audit, image build,
  Dockerfile lint, Trivy scan) and a separate release workflow that only publishes to GHCR
  after all CI checks pass and the built image itself passes a vulnerability scan.
- PowerShell deployment and rollback scripts with readiness waits, smoke tests, and
  automatic rollback on failure.
- Provisioned Grafana dashboard and Prometheus alert rules for availability, error rate,
  latency, and database reachability.

## Architecture

```mermaid
flowchart LR
    subgraph Client
        U[HTTP client]
    end

    subgraph "docker-compose stack"
        A["app (FastAPI, uvicorn)\nnon-root container"]
        D[("PostgreSQL 16\npersistent volume: pgdata")]
        P["Prometheus\nscrapes /metrics"]
        G["Grafana\ndashboards + alerts"]
    end

    U -->|HTTP :8000| A
    A -->|asyncpg| D
    P -->|scrape :8000/metrics| A
    G -->|PromQL| P
    U -->|:9090| P
    U -->|:3000| G
```

```mermaid
flowchart LR
    PR[Pull request] --> CI[CI workflow\nlint - unit - integration - audit - build - scan]
    CI -->|pass| Merge[Merge to main]
    Tag[Push version tag] --> Release[Release workflow]
    Release --> Validate[Re-run CI as a required gate]
    Validate -->|pass| Build[Build image]
    Build --> Scan[Trivy scan]
    Scan -->|clean| Push[Push to GHCR]
    Scan -->|vulnerable| Fail[Workflow fails, nothing published]
    Push --> Deploy["deploy.ps1 (local, manual)"]
    Deploy -->|smoke tests fail| Rollback[Automatic rollback]
```

## Technology stack

| Layer | Choice |
|---|---|
| Language / framework | Python 3.12, FastAPI, Uvicorn |
| Database / ORM | PostgreSQL 16, SQLAlchemy 2.0 (async, asyncpg), Alembic |
| Config / validation | Pydantic v2, pydantic-settings |
| Observability | prometheus-client, Prometheus, Grafana, JSON structured logging |
| Testing | pytest, pytest-asyncio, httpx |
| Containerization | Docker (multi-stage, non-root), Docker Compose |
| CI/CD | GitHub Actions, Trivy, hadolint, pip-audit, GHCR |
| Local deployment | PowerShell (`deploy/deploy.ps1`, `deploy/rollback.ps1`) |

## Prerequisites (Windows)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with the WSL2 backend,
  including Docker Compose v2 (bundled).
- Python 3.12+ (for running tests and scripts outside containers).
- PowerShell 5.1+ (bundled with Windows) for the deploy/rollback scripts.
- Git.

Verify your toolchain:

```bash
docker --version
docker compose version
python --version
git --version
```

## Local setup

1. Clone the repository and create your environment file:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set real values for `POSTGRES_PASSWORD` and `GRAFANA_ADMIN_PASSWORD`
   (the defaults are placeholders, not meant for anything beyond a throwaway local run).

2. (Optional, for running tests or scripts outside Docker) create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

## Environment configuration

All configuration is environment-driven (see `app/config.py` and `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `development` / `test` / `production` | `development` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `APP_VERSION` | Reported by `/version` | `0.1.0` |
| `GIT_SHA` | Reported by `/version`; set from CI build args | `unknown` |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database connection | see `.env.example` |
| `DATABASE_URL` | Overrides the constructed connection string entirely | unset |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | Grafana bootstrap credentials (compose only) | see `.env.example` |

No credentials are hardcoded anywhere in source or in the image; the container only
receives them via `--env-file` / compose `environment:`.

## Starting and stopping the stack

```bash
docker compose up -d --build
```

This builds the app image, starts PostgreSQL (with a healthcheck gate before the app
starts), runs Alembic migrations automatically on container start, then starts Prometheus
and Grafana.

Check status and logs:

```bash
docker compose ps
docker compose logs -f app
```

Stop everything (containers only, volumes preserved):

```bash
docker compose down
```

Stop and remove all data (fresh start):

```bash
docker compose down -v
```

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness: process is running |
| GET | `/ready` | Readiness: process **and** database reachable (503 if not) |
| GET | `/version` | Reports `version` and `git_sha` |
| GET | `/metrics` | Prometheus exposition format |
| POST | `/ships` | Create a ship |
| GET | `/ships` | List ships |
| GET | `/ships/{id}` | Get one ship |
| PATCH | `/ships/{id}` | Partially update a ship |
| DELETE | `/ships/{id}` | Delete a ship |

Example requests:

```bash
curl -X POST http://localhost:8000/ships \
  -H "Content-Type: application/json" \
  -d '{"name": "Discovery"}'

curl http://localhost:8000/ships

curl -X PATCH http://localhost:8000/ships/<id> \
  -H "Content-Type: application/json" \
  -d '{"status": "launched"}'

curl -X DELETE http://localhost:8000/ships/<id>
```

Interactive API docs are available at `http://localhost:8000/docs` while the app is running.

## Testing

Tests are split by how much infrastructure they need (`pyproject.toml` markers):

```bash
# Fast, no external services
pytest tests/unit -m unit

# Requires a reachable PostgreSQL (see below)
pytest tests/integration -m integration

# Requires a working Docker daemon; builds and runs the real image via compose
pytest tests/docker -m docker
```

For integration tests, point `TEST_DATABASE_URL` at any reachable PostgreSQL instance, for
example one started just for testing:

```bash
docker run -d --name shipyard-test-db -p 5432:5432 \
  -e POSTGRES_USER=shipyard -e POSTGRES_PASSWORD=shipyard -e POSTGRES_DB=shipyard_test \
  postgres:16-alpine

set TEST_DATABASE_URL=postgresql+asyncpg://shipyard:shipyard@localhost:5432/shipyard_test
pytest tests/integration -m integration
```

Lint and format checks (same as CI):

```bash
ruff check .
ruff format --check .
```

A standalone smoke-test script exercises a running instance end-to-end (health, ready,
version, metrics, full ships CRUD lifecycle):

```bash
python scripts/smoke_test.py --base-url http://localhost:8000
```

## CI/CD workflows

- **`.github/workflows/ci.yml`** runs on every pull request and push to `main`, and is also
  reusable via `workflow_call`. Jobs: `lint` (ruff), `unit-tests`, `integration-tests`
  (PostgreSQL service container), `dependency-scan` (`pip-audit`), and `docker-build`
  (hadolint + image build + Trivy scan). All jobs must pass before a PR can merge if branch
  protection requires them.
- **`.github/workflows/release.yml`** triggers only on version tags (`vX.Y.Z`). It first
  calls `ci.yml` as a required gate, then builds the image, scans it with Trivy a second
  time, and only pushes to `ghcr.io/<owner>/shipyard` if that scan is clean. A failed
  validation or scan never results in a published image.
- Third-party actions are pinned to full commit SHAs (with the version as a comment) rather
  than mutable tags, to resist supply-chain tampering.
- Tokens use the narrowest scope each job needs: `contents: read` everywhere, with
  `packages: write` added only to the publish job.

## Image versioning and release procedure

1. Merge changes to `main` once CI is green.
2. Tag the release commit: `git tag v1.2.3 && git push origin v1.2.3`.
3. The release workflow builds, scans, and pushes:
   - `ghcr.io/<owner>/shipyard:1.2.3`
   - `ghcr.io/<owner>/shipyard:1.2`
   - `ghcr.io/<owner>/shipyard:sha-<commit>`
   - `ghcr.io/<owner>/shipyard:latest` (skipped for pre-release tags like `v1.2.3-rc1`)
4. The workflow log prints the immutable digest reference
   (`ghcr.io/<owner>/shipyard@sha256:...`) — prefer this over a mutable tag when deploying.

## Deployment and rollback

GitHub-hosted runners cannot reach a developer's Windows `localhost`, so deployment is a
deliberate, separate step run locally after the release workflow has published an image.

```powershell
# Deploy a specific image (tag or, preferably, digest)
.\deploy\deploy.ps1 -Image ghcr.io/<owner>/shipyard:1.2.3

# Roll back to the previously running release
.\deploy\rollback.ps1
```

`deploy.ps1`:

1. Validates the image reference.
2. Stops the currently running `shipyard-app` container and preserves it (stopped, not
   removed) as `shipyard-app-previous`.
3. Pulls the new image and starts it on the compose network so it can reach `db`.
4. Waits for `/ready`, then runs smoke tests (health/ready/version/metrics + a full ships
   CRUD round trip).
5. On any failure, automatically restarts `shipyard-app-previous` and verifies it is
   healthy again before exiting non-zero.
6. On success, records the deployed version/digest/timestamp in `deploy/state.json` and
   keeps the previous container as the rollback fallback.

`rollback.ps1` restores `shipyard-app-previous` on demand (e.g. a problem noticed after the
fact) and verifies the restored service with the same readiness/smoke checks. Rollback only
ever swaps the application container — it never touches the database or runs migrations in
reverse. See [docs/runbooks/rollback.md](docs/runbooks/rollback.md) for the compatibility
constraints this implies for schema changes.

Logs from both scripts are written to `deploy/logs/`.

## Monitoring

- Prometheus: `http://localhost:9090` — scrapes `app:8000/metrics` every 15s.
- Grafana: `http://localhost:3000` (login from `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`)
  — the "Shipyard Overview" dashboard is provisioned automatically and shows request rate,
  5xx error ratio, p50/p95 latency, service `up`, database reachability, and the running
  `app_info` version/SHA.
- Alert rules (`monitoring/prometheus/alert.rules.yml`): `ShipyardServiceDown`,
  `ShipyardHighErrorRate` (>5% 5xx over 5m), `ShipyardHighLatency` (p95 > 1s over 5m),
  `ShipyardDatabaseUnreachable`.
- Metric labels are bounded by design (`method`, route **template** — not raw URLs —, and
  numeric `status`) to avoid unbounded cardinality.

## Security scanning and vulnerability policy

See [SECURITY.md](SECURITY.md) for the full policy. Summary: `pip-audit` gates dependency
vulnerabilities, `hadolint` gates Dockerfile issues, and `trivy` gates the built image
(CRITICAL/HIGH with a fix available fails the build) both in CI and again immediately
before a release image is pushed.

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| `/ready` returns 503 | Database unreachable | `docker compose logs db`, `docker compose ps` |
| App container restarting in a loop | Migrations failing against the DB | `docker compose logs app` (entrypoint retries `alembic upgrade head` for ~60s before giving up) |
| `deploy.ps1` exits with code 2 | New image failed readiness/smoke tests and no previous container existed to roll back to | Check `deploy/logs/deploy.log` and `deploy/logs/failed-deploy-*.log` |
| Grafana shows "No data" | Prometheus can't reach the app, or the app hasn't served any traffic yet | Check Prometheus Targets page at `http://localhost:9090/targets`; send traffic with `scripts/smoke_test.py` |
| Port already in use | Another process is bound to 8000/5432/9090/3000 | Change the published port in `docker-compose.yml` or stop the conflicting process |

See also [docs/runbooks/](docs/runbooks/) for incident-style recovery procedures.

## Known limitations

- There is no authentication/authorization layer; this is a demonstration API, not a
  hardened multi-tenant service.
- Rollback restores the previous application container only; it does not reverse database
  migrations. Schema changes must stay backward-compatible with the prior release for
  rollback to be safe (see the rollback runbook).
- The GitHub Actions workflows cannot deploy to a developer's local machine; deployment is
  an intentionally separate, manual PowerShell step.
- No self-hosted runner is configured; CI/release run entirely on GitHub-hosted runners.
- Secret scanning (e.g. gitleaks) is not yet wired into CI.

## Reproducible demo

```bash
cp .env.example .env
docker compose up -d --build
python scripts/smoke_test.py --base-url http://localhost:8000
```

Then open `http://localhost:3000` (Grafana) to watch the dashboard populate as the smoke
test script generates traffic, and `http://localhost:9090/targets` to confirm Prometheus is
scraping the app.
