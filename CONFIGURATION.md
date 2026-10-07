# Configuration

`.env.example` is safe to copy and has no private host, tenant, credential, certificate, or production executor. `scripts/init_env.py` creates random `POSTGRES_PASSWORD`, `POSTGRES_ADMIN_PASSWORD`, and `BOOTSTRAP_TOKEN` values without printing them.

| Section | Main settings | Safe default |
|---|---|---|
| Application | `APP_ENV`, `PUBLIC_ORIGIN`, `WEB_BIND`, `WEB_PORT` | development / loopback |
| Database | `DATABASE_URL`, `DB_NAME`, `DB_USER` | SQLite development; PostgreSQL Compose production |
| Auth | `BOOTSTRAP_TOKEN`, `SESSION_HOURS`, `COOKIE_SECURE` | no users; secure cookies outside loopback |
| AI | `AI_PROVIDER`, provider URL/model/token | mock provider |
| Ingestion | `ENABLE_DEMO`, `MAX_REQUEST_BYTES` | demo disabled, bounded body |
| Connectors | `CORE_MODE`, optional Core URL/token/CA | standalone |
| SOAR | `SOAR_EXECUTOR`, protected assets/networks | `dry_run` |
| TLS | `ALLOW_INSECURE_HTTP`, `TRUSTED_HTTP_HOSTS` | HTTPS required for non-loopback |
| Limits | timeouts, `MAX_EVIDENCE`, context/response budgets | bounded values |

Provider and connector credentials are server-only. They are not returned by settings endpoints, placed in browser JavaScript, or accepted from request bodies. Production requires PostgreSQL and rejects superuser-style database identities. External executors fail closed unless a future verified plugin is implemented.
