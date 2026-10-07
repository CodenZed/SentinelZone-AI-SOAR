# Contributing

Create focused changes with tests and documentation. Do not add real credentials, private IPs, certificates, database dumps, lab paths, or unverified vendor claims. Keep source provenance and migration safety intact. New connectors must include a configuration schema, bounded transport, normalization tests, provenance tests, tenant checks, and a clear PASS/UNVERIFIED/NOT IMPLEMENTED status.

Run `python -m pytest -q`, `python -m ruff check app tests migrations scripts`, `node frontend/build.mjs`, and `node --test frontend/tests/*.test.mjs`. Live integrations require a disposable environment and must never be labeled verified from mocks.
