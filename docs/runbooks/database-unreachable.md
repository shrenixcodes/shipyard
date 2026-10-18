# Runbook: `/ready` reports database unreachable

## Symptoms

- `GET /ready` returns `503` with `{"checks": {"database": "failed"}}`.
- Grafana's "Database reachable" panel shows `0`.
- The `ShipyardDatabaseUnreachable` Prometheus alert is firing.
- `/health` still returns `200` — the process itself is fine, only its database dependency
  is down. This distinction is deliberate: don't restart the app container for this before
  checking the database first.

## Diagnosis

1. Check the database container is up:

   ```bash
   docker compose ps db
   docker compose logs --tail=100 db
   ```

2. Check the app can resolve/reach it on the compose network:

   ```bash
   docker compose exec app python -c "import socket; print(socket.gethostbyname('db'))"
   ```

3. Check credentials match between `app` and `db` (both read from the same `.env`):

   ```bash
   docker compose exec app env | grep POSTGRES
   docker compose exec db env | grep POSTGRES
   ```

4. Check Postgres itself is accepting connections and not out of disk:

   ```bash
   docker compose exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   docker compose exec db df -h /var/lib/postgresql/data
   ```

## Common causes and fixes

| Cause | Fix |
|---|---|
| `db` container not yet healthy when `app` started | `docker compose restart app` — the entrypoint retries migrations/connections for ~60s, but a long DB startup can outlast that; restart the app once `db` is healthy |
| Wrong credentials in `.env` | Fix `.env`, then `docker compose up -d --force-recreate app` |
| `pgdata` volume corrupted or disk full | Free disk space; if corrupted, this requires restoring from a backup — there is no automated backup/restore in this project, so this is a hard limitation to be aware of before relying on it beyond local/demo use |
| Network misconfiguration (custom `-Network` passed to `deploy.ps1` that isn't the compose network) | Re-run `deploy.ps1` with the default network or verify `docker network ls` shows `shipyard_shipyard-net` attached to both containers |

## Verifying recovery

```bash
curl http://localhost:8000/ready
```

Expect `{"status": "ok", "checks": {"database": "ok"}}`. Confirm the Prometheus alert
clears and the Grafana panel returns to `1`.
