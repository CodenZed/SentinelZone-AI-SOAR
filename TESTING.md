# Testing

Run the isolated checks from the repository root:

```sh
python -m pytest -q --tb=short
python -m ruff check app tests migrations scripts
node frontend/build.mjs
node --test frontend/tests/*.test.mjs
python scripts/smoke_standalone.py
```

The Python suite includes clean installation, migrations, tenant isolation, authentication, RBAC, ingestion duplicates/conflicts/provenance, evidence membership, AI citations, prompt injection boundaries, provider failure, unknown telemetry, proposals, self-approval, expiry, dry-run execution/verification/rollback, crash/restart claims, protected targets, audit, connector mocks, and API contracts. The frontend suite covers escaping, route contracts, role capabilities, and browser secret handling.

Live PostgreSQL, Docker, vendor, and live model tests are separate gates. They must be run only against disposable, explicitly named environments and reported as NOT RUN until actually executed.
