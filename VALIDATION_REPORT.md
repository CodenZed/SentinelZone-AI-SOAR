# Validation report — v0.30.0-rc.1

Date: 2026-10-07. Scope: the standalone product extracted from the supplied v0.29.1 source ZIP. No external SentinelZone Core, dashboard, lab database, private network, live model, firewall, endpoint, or credential was accessed.

| Gate | Result | Evidence |
|---|---|---|
| Canonical source preserved | PASS | Original ZIP copied to `work/original`; SHA-256 `f8515d43da81f3e2ad4f667b3ec1fcc2091d23c33845e36feb67d97ef4c8519b`; inventory and coupling map recorded |
| Supplied baseline suite | PASS | 168 passed, 1 skipped, 0 failed; the skip is live PostgreSQL without `TEST_DATABASE_URL` |
| Standalone backend suite | PASS | 185 passed, 1 skipped, 1 known Starlette/httpx deprecation warning |
| Lint | PASS | Ruff reports all checks passed |
| SQLite migrations | PASS | Alembic 0001 → 0002 → 0003; upgrade/downgrade/upgrade and schema checks in suite |
| PostgreSQL migration SQL | PASS | Offline SQL compilation covered; live PostgreSQL NOT RUN |
| Product ingestion | PASS | Schema validation, provenance, UTC normalization, idempotency, conflicts, tenant isolation, atomicity, request limits |
| Auth/RBAC | PASS | Bootstrap, password hashing, sessions, CSRF/origin, throttling, Viewer/Analyst/Operator/Admin separation |
| AI safety | PASS | Redaction, bounded context, prompt boundary, citations, selected evidence membership, provider failure, mock/OpenAI/local/Ollama contracts |
| SOAR safety | PASS | Independent approval, self-approval denial, expiry, protected targets, durable claims, dry-run execution, verification, rollback, restoration |
| Frontend build | PASS | `node frontend/build.mjs` |
| Frontend contract/security tests | PASS | 5 Node tests: escaped strings, role capabilities, simulation labels, API route contract, no browser token storage/unsafe sinks |
| Loopback HTTP product smoke | PASS | Bootstrap → sessions → users → TEST demo → AI → independent approval → dry-run execute/verify → duplicate denial → rollback/restoration → audit |
| Browser visual inspection | PASS | Local preview showed sign-in, overview, TEST incident, evidence, AI validation notice, and proposal form |
| Docker runtime | NOT RUN | Docker unavailable in the validation environment |
| Live PostgreSQL | NOT RUN | No disposable PostgreSQL service supplied |
| Live AI inference | NOT RUN | No provider credentials/model endpoint supplied |
| Live vendor integrations | NOT IMPLEMENTED / UNVERIFIED | Fail-closed skeletons and mocks only |

`PASS` in this report means the stated local scope passed. It does not claim production readiness or live vendor compatibility. The browser proposal submit was not used as evidence because the Codex automatic approval review hit a usage limit; backend HTTP smoke covered the same workflow in an isolated test environment.
