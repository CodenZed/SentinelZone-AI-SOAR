# Changelog

## v0.30.0-rc.1 — 2026-10-07

- Converted the Core-dependent integration package into a standalone product with product-owned evidence and incident storage.
- Added additive Alembic migration 0003, authenticated ingestion, source idempotency, provenance, browser bootstrap/sessions, password hashing, CSRF, and Viewer role.
- Added generic REST/webhook connector ports, optional SentinelZone importer, explicit Wazuh/Splunk skeletons, and fail-closed executor plugin namespaces.
- Added standalone dark SOC web interface with TEST/REAL/REPLAY/UNKNOWN/DRY RUN labels and AI citation-vs-correctness distinction.
- Added Ollama provider, product API views, deterministic demo dataset, frontend build/tests, Compose PostgreSQL/backend/frontend deployment, and public product documentation.
- Preserved v0.29.x AI/SOAR migrations, approval rules, citation validation, provenance, durable claims, verification, rollback, and audit behavior.

## v0.29.1-sentinelzone — historical input

The supplied release was an optional SentinelZone integration package. Its validation and limitations are retained as historical source provenance; they are not the architecture or default configuration of this release.
