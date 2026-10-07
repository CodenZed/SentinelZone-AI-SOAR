# SentinelZone AI/SOAR

SentinelZone AI/SOAR is a standalone, self-hosted investigation and human-approved response platform. It owns its PostgreSQL schema, normalized incidents and evidence, AI run ledger, approvals, execution claims, verification, rollback, audit records, REST API, and web interface. SentinelZone Core is an optional read-only connector; a fresh installation does not require it.

```text
Generic REST / webhook / optional adapters
                    │
             normalization + provenance
                    │
          product-owned PostgreSQL evidence
              ┌─────┴─────┐
          AI investigation   SOAR proposals
              └─────┬─────┘
          approval → execute → verify → rollback
                    │
             standalone web interface
```

## Quick start

```sh
cp .env.example .env
python scripts/init_env.py --generate-secrets
docker compose up -d --build --wait
```

Open `http://localhost:8080`. Bootstrap the first administrator using the one-time `BOOTSTRAP_TOKEN`, then remove that value from the private environment. Keep `AI_PROVIDER=mock`, `CORE_MODE=standalone`, and `SOAR_EXECUTOR=dry_run` for a deterministic TEST walkthrough. Enable `ENABLE_DEMO=true` only when you intentionally want the labeled demo dataset.

Native development uses SQLite, `python -m alembic upgrade head`, `node frontend/build.mjs`, and `python scripts/serve_dev.py`. See [INSTALL.md](INSTALL.md).

## Product boundaries

- Tenant-scoped, authenticated versioned ingestion: `POST /v1/ingest/events` and `POST /v1/ingest/incidents`.
- Stable source identity, idempotent replays, provenance, UTC timestamps, request limits, and structured errors.
- Viewer, Analyst, Operator, and Admin roles. An Analyst cannot approve; an Operator cannot approve their own proposal; Admin is not implicitly an Operator.
- AI receives bounded, selected, redacted `UNTRUSTED EVENT DATA`; it has no tools or action authority. Citation validation is separate from semantic correctness.
- Dry-run is always available and always labeled. Real pfSense, Shuffle, Wazuh, and Splunk execution is disabled or unverified until a verified contract and state-query adapter exist.
- Durable at-most-once operation claims prevent blind redispatch after restart. Exactly-once vendor effects are never claimed.

## Documentation

[ARCHITECTURE.md](ARCHITECTURE.md) · [INSTALL.md](INSTALL.md) · [CONFIGURATION.md](CONFIGURATION.md) · [API.md](API.md) · [CONNECTORS.md](CONNECTORS.md) · [AI.md](AI.md) · [SOAR.md](SOAR.md) · [SECURITY.md](SECURITY.md) · [RBAC.md](RBAC.md) · [BACKUP_RESTORE.md](BACKUP_RESTORE.md) · [UPGRADE.md](UPGRADE.md) · [TESTING.md](TESTING.md) · [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

The optional adapter is documented in [docs/integrations/sentinelzone.md](docs/integrations/sentinelzone.md). The web application is in `frontend/` and uses only this product API.

## Release status

Version `v0.30.0-rc.1` is a release candidate. The isolated suite, SQLite migrations, frontend build, UI contract tests, and loopback HTTP workflow are validated here. Live PostgreSQL runtime, Docker startup, live model inference, vendor APIs, and production TLS deployment remain environment-specific gates. See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

MIT licensed. Dependency notices and the CycloneDX SBOM are included.
