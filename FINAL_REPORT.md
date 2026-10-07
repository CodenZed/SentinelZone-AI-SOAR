# Final report — SentinelZone AI/SOAR v0.30.0-rc.1

## Product status

RELEASE CANDIDATE. The package is standalone by default, owns its evidence and incident model, and runs without SentinelZone Core or an existing dashboard. Production readiness is not claimed because live PostgreSQL, Docker, live AI, TLS deployment, and vendor executors were not available for verification.

## Architecture and compatibility

The new `EvidenceRepository` port and `SQLEvidenceRepository` make product storage the default context source. Migration 0003 adds tenants, incidents, evidence events, memberships, assets, browser sessions, password hashes, and bootstrap state without deleting v0.29.x AI/SOAR claims. SentinelZone remains an optional read-only adapter under `app/connectors/sentinelzone/`; Wazuh and Splunk are explicit skeletons.

The lab assumptions removed from operational defaults include Core/dashboard addresses, fixed tenant, shared database identity, external dashboard dependence, and fixture-backed startup. Historical supplied reports and the original source patch remain under `source/` as provenance and are not runtime configuration.

## Validation

- Backend baseline: PASS — 168 passed, 1 skipped.
- Standalone backend: PASS — 185 passed, 1 skipped, 1 known deprecation warning.
- Ruff: PASS.
- SQLite migration roundtrip and schema drift: PASS.
- PostgreSQL SQL generation: PASS; live PostgreSQL: NOT RUN.
- Security/RBAC, tenant isolation, ingestion, provenance, citation, prompt boundary, provider failure, durable claim, protected target, dry-run, verification, rollback, and audit tests: PASS.
- Frontend build: PASS. Frontend contract/security tests: PASS — 5 passed.
- Isolated loopback HTTP smoke: PASS, covering bootstrap, sessions, users, TEST ingestion, mock AI, independent approval, dry-run execution/verification, duplicate execution denial, rollback/restoration, and audit.
- Browser visual preview: PASS for sign-in, overview, TEST incident, evidence, AI result, and proposal form. Final browser proposal submission was not used as evidence because automatic approval review hit a Codex usage limit; no review bypass was attempted.
- Docker runtime, live PostgreSQL, live AI, current SentinelZone, Wazuh, Splunk, pfSense, Shuffle, and Windows deployment: NOT RUN or NOT IMPLEMENTED as stated in `VALIDATION_REPORT.md`.

## Release contents

The release contains backend, migrations, contracts, standalone frontend, Compose deployment, environment generator, deterministic TEST example, connector/executor interfaces, API/OpenAPI, SBOM/notices, GitHub CI, and product documentation. `scripts/package_release.py` creates:

`sentinelzone-ai-soar-v0.30.0-rc.1-source.zip`

`sentinelzone-ai-soar-v0.30.0-rc.1-deploy.tar.gz`

`sentinelzone-ai-soar-v0.30.0-rc.1-SHA256SUMS.txt`

The generated `release-manifest.json`, `SHA256SUMS`, SBOM, validation report, and known limitations are included in the source archive. Hashes are recorded in the checksum file generated from the final clean tree.

The exact added and changed path inventory is in
[`docs/CHANGESET-v0.30.0-rc.1.md`](docs/CHANGESET-v0.30.0-rc.1.md). The
archive manifest records a SHA-256 for every packaged file.

## GitHub publication

Create a new repository, review the generated archive and checksums, then from the clean product root run:

```sh
git init
git add .
git commit -m "Release SentinelZone AI/SOAR v0.30.0-rc.1"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```

Create a tagged release only after independently running the PostgreSQL and Docker gates, then attach the ZIP, deployment TAR, checksum file, SBOM, `VALIDATION_REPORT.md`, and `KNOWN_LIMITATIONS.md`.
