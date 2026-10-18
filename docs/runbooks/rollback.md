# Runbook: Rolling back a bad release

## When to use this

- `deploy.ps1` already attempted an automatic rollback and failed (exit code 2), or
- A release was deployed successfully but a problem was noticed later (elevated error rate,
  bad business logic, etc.) and you need to restore the previous version.

## What rollback does and does not do

`rollback.ps1` restores the application container preserved by the last `deploy.ps1` run
(`shipyard-app-previous`). It:

- **Does** stop and discard the current (bad) container, preserving its logs under
  `deploy/logs/`.
- **Does** verify the restored container passes the same readiness and smoke checks used
  during deploy.
- **Does not** touch the PostgreSQL container, its data, or run any Alembic migration.

### Why migrations are not rolled back automatically

Application rollback and database migration rollback are different problems. If release
`N` added a migration that release `N-1`'s code does not understand (e.g. a column it never
selects, or a renamed column it still expects under the old name), rolling back the
*application* while the *schema* stays on `N` can break release `N-1` outright.

This project's migrations are written to be backward-compatible with the previous
application release wherever possible (additive changes: new nullable columns, new tables,
new indexes — never a rename or a drop in the same release that also removes the old
read path). Under that discipline, rolling back the application container alone is safe.

If a future migration cannot be made backward-compatible, it must ship as two releases:
first an additive migration deployed and verified, then the behavior change in a later
release — never both at once.

## Procedure

1. Confirm there is a fallback container to restore:

   ```powershell
   docker ps -a --filter "name=shipyard-app-previous"
   ```

   If none exists, there is nothing to roll back to — you must deploy a known-good image
   instead with `deploy.ps1`.

2. Run the rollback script:

   ```powershell
   .\deploy\rollback.ps1
   ```

3. Confirm the output reports `rollback complete and service availability verified`, and
   check the reported version/SHA matches what you expect:

   ```powershell
   curl http://localhost:8000/version
   ```

4. Inspect `deploy/logs/pre-rollback-*.log` for the failing release's logs to drive the
   incident follow-up / root cause fix.

5. Once the underlying issue is fixed and a new image is published, redeploy normally with
   `deploy.ps1` — this creates a fresh `shipyard-app-previous` fallback pointing at the
   version you just rolled back to.

## If rollback itself fails

`rollback.ps1` exits with code 2 if the restored container does not become ready or fails
smoke tests. In that case:

- Check `docker compose logs db` — if the database itself is the problem, rollback cannot
  fix that; see [docs/runbooks/database-unreachable.md](database-unreachable.md).
- Check `deploy/logs/deploy.log` for the exact failing step.
- As a last resort, restore service by starting a known-good image fresh with
  `deploy.ps1 -Image <last known-good tag or digest>`.
