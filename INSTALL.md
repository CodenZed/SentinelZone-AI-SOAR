# Installation

## Docker Compose

Requirements: Docker Engine with Compose v2. From a clean checkout:

```sh
cp .env.example .env
python scripts/init_env.py --generate-secrets
docker compose config --quiet
docker compose up -d --build --wait
```

Compose starts a dedicated PostgreSQL service, backend, and standalone frontend. The backend container listens only inside the Compose network; the UI is bound to `WEB_BIND`/`WEB_PORT`, which default to loopback `127.0.0.1:8080`. Persistent data is in the `postgres-data` volume. Do not use `docker compose down -v` on a deployed instance because it removes durable operation claims.

Open the UI and bootstrap the first Admin. Create an Analyst and a different Operator. Configure an AI provider only after the base service is healthy. Load TEST data, investigate, propose a DRY-RUN action, approve it with the Operator, execute, verify, rollback, and inspect Audit.

## Native development

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock.txt
python scripts/init_env.py --profile development
python -m alembic upgrade head
node frontend/build.mjs
python scripts/serve_dev.py
```

This mode uses SQLite, mock AI, standalone evidence storage, and dry-run. It is suitable for tests and local development, not a production deployment.

## First-run safety

No default user or production credential is shipped. Passwords are salted PBKDF2 hashes, browser sessions are expiring and HttpOnly, mutating browser requests require same-origin CSRF protection, and bootstrap is a one-time state transition. Remove the bootstrap secret after creating the first Admin. Set `COOKIE_SECURE=true` and serve the UI over HTTPS outside loopback.

## Deployment gates

The supplied environment cannot prove Docker startup, live PostgreSQL locking, live AI inference, vendor APIs, or Windows native deployment. These are explicitly NOT RUN in the validation report.
