# Security Policy

## Reporting a vulnerability

If you discover a security issue in this project, please report it privately rather than
opening a public issue. Email the maintainer listed in the repository's commit history with:

- A description of the issue and its potential impact.
- Steps to reproduce, including affected endpoint(s) or file(s).
- Any suggested remediation, if known.

You should receive an acknowledgement within 5 business days. Please allow a reasonable
period for a fix before any public disclosure.

## Supported versions

Only the most recently published container image tag (and the `main` branch) is supported
with security fixes. There is no long-term support branch for this portfolio project.

## Vulnerability scanning in CI

Every pull request and push to `main` runs:

- **`pip-audit`** against `requirements.txt` — fails the build on any known vulnerability in
  runtime dependencies (see `.github/workflows/ci.yml`, job `dependency-scan`).
- **`hadolint`** against the `Dockerfile` — fails on Dockerfile best-practice violations at
  `error` severity or above (job `docker-build`).
- **`trivy`** container image scan — fails the build on any `CRITICAL` or `HIGH` severity
  vulnerability with an available fix (`ignore-unfixed: true`). This runs again before a
  release image is pushed to GHCR (`.github/workflows/release.yml`), so a vulnerable image
  is never published even if an earlier scan was skipped.

### Severity policy

| Severity | CI behavior |
|---|---|
| CRITICAL / HIGH (fixed upstream) | Build fails, merge/release blocked |
| CRITICAL / HIGH (no fix available yet) | Logged, does not fail the build (`ignore-unfixed`) |
| MEDIUM / LOW | Logged for visibility, does not fail the build |

### Accepted exceptions

None at this time. If an exception is ever required (e.g. a HIGH-severity finding with no
upstream fix and no practical mitigation), it must be documented here with: the CVE ID, why
it cannot be remediated immediately, the compensating control, and a target re-evaluation
date. Do not silently suppress scanner findings.

## Secrets handling

- No credentials are committed to this repository. `.env` is git-ignored; `.env.example`
  contains placeholders only.
- Container images are built without embedding `.env` files, private keys, or tokens
  (enforced by `.dockerignore`).
- CI workflows use the default, auto-expiring `GITHUB_TOKEN` scoped to the minimum
  permissions each job needs (`contents: read`, plus `packages: write` only in the
  publish job of `release.yml`). No long-lived registry credentials are stored.

## Runtime security posture

- The application container runs as a non-root user (`shipyard`, uid 1000).
- The container does not request privileged mode, extra capabilities, or host mounts.
- The database is not published to the host network in `docker-compose.yml`; only the
  application, Prometheus, and Grafana ports are exposed.
- Database credentials are supplied via environment variables sourced from a local `.env`
  file, never hardcoded in source or images.

## Known limitations

This is a portfolio/demonstration project, not an audited production system. In particular:

- Vulnerability scanning covers the application image and its direct Python dependencies;
  it does not include a full software composition analysis or license audit.
- There is no automated secret-scanning (e.g. gitleaks/truffleHog) wired into CI yet.
- Authentication/authorization is intentionally out of scope for the demo API.

Running a scanner and reporting zero findings does not by itself constitute a complete
security review — treat CI results as one input among several when assessing risk.
