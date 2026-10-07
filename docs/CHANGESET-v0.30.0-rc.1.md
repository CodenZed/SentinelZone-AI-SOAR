# v0.30.0-rc.1 change inventory

This inventory compares the canonical extracted v0.29.1 source tree with the
release tree. Runtime caches and generated release checksums are excluded.

## Added files

`AI.md`, `BACKUP_RESTORE.md`, `CODE_OF_CONDUCT.md`, `CONFIGURATION.md`,
`CONNECTORS.md`, `CONTRIBUTING.md`, `FINAL_REPORT.md`, `RBAC.md`, `SECURITY.md`,
`SOAR.md`, `UPGRADE.md`, `app/ai/providers/ollama.py`, `app/api/identity.py`,
`app/api/product.py`, `app/connectors/base.py`,
`app/connectors/generic_rest/__init__.py`, `app/connectors/sentinelzone/client.py`,
`app/connectors/sentinelzone/importer.py`, `app/connectors/sentinelzone/mapping.py`,
`app/connectors/splunk/__init__.py`, `app/connectors/wazuh/__init__.py`,
`app/connectors/webhook/__init__.py`, `app/ingestion/contracts.py`,
`app/ingestion/service.py`, `app/repositories/base.py`, `app/repositories/sql.py`,
`app/security/passwords.py`, `app/soar/executors/generic_webhook/__init__.py`,
`app/soar/executors/pfsense/__init__.py`, `app/soar/executors/shuffle/__init__.py`,
`contracts/asset-input.schema.json`, `contracts/connector-config.schema.json`,
`contracts/ingest-events.schema.json`, `contracts/ingest-incidents.schema.json`,
`deploy/init-db.sh`, `docs/CHANGESET-v0.30.0-rc.1.md`,
`docs/integrations/sentinelzone.md`, `examples/demo.json`,
`frontend/build.mjs`, `frontend/Dockerfile`, `frontend/nginx.conf`,
`frontend/package-lock.json`, `frontend/package.json`, `frontend/src/api.mjs`,
`frontend/src/app.mjs`, `frontend/src/index.html`, `frontend/src/styles.css`,
`frontend/tests/ui.test.mjs`, `migrations/versions/0003_standalone.py`,
`playbooks/block_ip.yml`, `scripts/serve_dev.py`, `scripts/smoke_standalone.py`,
`tests/test_standalone.py`.

The frontend `dist/` files are generated from the checked-in source and are
included in the release archives.

## Changed files

`BACKEND_REQUIRED_CHANGES.md`, `.env.example`, `.github/workflows/test.yml`,
`API.md`, `ARCHITECTURE.md`,
`CHANGELOG.md`, `DASHBOARD_INTEGRATION.md`, `INSTALL.md`, `INTEGRATION.md`,
`KNOWN_LIMITATIONS.md`, `README.md`, `TESTING.md`, `VALIDATION_REPORT.md`,
`docker-compose.native.yml`, `docker-compose.yml`, `scripts/init_env.py`,
`scripts/package_release.py`, `app/__init__.py`, `app/ai/context/selector.py`,
`app/ai/investigation/runner.py`, `app/api/actions.py`, `app/api/ai.py`,
`app/api/health.py`, `app/api/responses.py`, `app/cli.py`, `app/config.py`,
`app/connectors/core_backend.py`, `app/connectors/http.py`,
`app/connectors/mapping.py`, `app/contracts.py`,
`app/db/models.py`, `app/main.py`, `app/security/auth.py`,
`app/soar/executors/factory.py`, `app/soar/proposals/policy.py`,
`contracts/action-proposal.schema.json`, `contracts/action-view.schema.json`,
`contracts/ai-output.schema.json`, `contracts/ai-run.schema.json`,
`contracts/api-error.schema.json`, `contracts/execution-receipt.schema.json`,
`contracts/executor-config.schema.json`, `contracts/incident-context.schema.json`,
`contracts/playbook.schema.json`, `contracts/verification-report.schema.json`,
`docs/DEPENDENCIES.json`, `docs/INTEGRATION.md`, `docs/openapi.json`,
`docs/VALIDATION_REPORT.md`, `docs/validation-summary.json`, `licenses/` metadata,
`tests/test_adapters.py`, `tests/test_playbooks.py`,
`tests/test_sentinelzone_contracts.py`, `THIRD_PARTY_NOTICES.md`, and the
generated `SBOM.cdx.json`.

The historical `playbooks/block_ip_lab.yml` was removed in favor of the generic
`playbooks/block_ip.yml`; its behavior and safety tests are preserved.
