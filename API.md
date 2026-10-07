# API

The API is versioned under `/v1`. All routes except `/health`, `/openapi.json`, and bootstrap/login require a tenant-scoped bearer token or browser session. JSON bodies are schema-validated, bounded, and return `{ "detail": { "code": "..." } }` on failure. OpenAPI is exported at `docs/openapi.json`.

## Ingestion

`POST /v1/ingest/events` accepts `{ "events": [...] }`; `POST /v1/ingest/incidents` accepts `{ "incidents": [...] }`. Each record requires `source_id` and `external_id`. Incident event references must already exist in the same tenant and data mode. Identical retries return `duplicate: true`; a changed payload with the same source identity returns 409. `event_time` is normalized to UTC. Provenance is retained as structured metadata.

## Investigation

`POST /v1/ai/analyze` with `{ "incident_id": "..." }` creates a persisted synchronous run. `GET /v1/ai/runs/{run_id}` and `GET /v1/incidents/{id}/analyses` retrieve runs. The response exposes `data_mode`, `trusted`, `validation_status`, citations, missing telemetry, and safe metadata. It never exposes hidden reasoning or raw provider output.

## SOAR

`POST /v1/actions` creates a proposal. `POST /v1/actions/{id}/approve`, `/reject`, `/execute`, and `/rollback` require an Operator and server-side eligibility checks. `/execute` is dry-run by default and its response states `effect_scope=simulated`; `verification_result` and `restoration_verified` are tri-state.

## Identity and product views

`POST /v1/auth/bootstrap`, `/login`, `/logout`; `GET /v1/auth/me`; `GET/POST/PATCH /v1/users`; `GET /v1/overview`, `/incidents`, `/events`, `/assets`, `/integrations`, `/audit`, `/settings`, and `/health`. Use pagination `limit` and `offset` where exposed. The browser UI calls only these product routes.
