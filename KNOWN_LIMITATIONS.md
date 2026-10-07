# Known limitations

Status terms are deliberate: PASS, FAIL, PARTIAL, NOT RUN, NOT IMPLEMENTED, UNVERIFIED, and NOT APPLICABLE.

1. Live PostgreSQL runtime and locking were NOT RUN in this environment. SQLite migration/runtime passed; PostgreSQL SQL generation is checked offline.
2. Docker Compose build/start was NOT RUN because Docker was unavailable. Compose syntax and health dependencies are supplied, not runtime evidence.
3. OpenAI, OpenAI-compatible, and Ollama inference were tested with mocks only. A health endpoint does not prove model inference or semantic correctness.
4. pfSense, Shuffle, Wazuh, and Splunk live integrations are NOT IMPLEMENTED or UNVERIFIED and fail closed. Mock adapter tests do not prove interoperability.
5. SentinelZone Core is optional and UNVERIFIED against a current deployment. The adapter uses read-only REST only; no Core DB/source/dashboard is required.
6. OIDC/SSO, distributed queues, cancellation, audit export, retention automation, and multi-worker AI recovery are not implemented.
7. Audit is application-append-only, not tamper-proof against a database owner. Backups must preserve operation claims.
8. Durable dispatch is at-most-once at the application boundary. It cannot guarantee exactly-once remote effects or resolve conflicting proposals across vendors.
9. Regex redaction cannot identify every encoded or unlabeled secret. Keep raw unrestricted logs out of evidence summaries.
10. Production TLS, reverse-proxy limits, PostgreSQL grants, backup retention, and monitoring remain deployment responsibilities.
