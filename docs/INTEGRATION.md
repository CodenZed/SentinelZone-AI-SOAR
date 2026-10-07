# Integration model

SentinelZone AI/SOAR is a standalone product. The product API is the primary
integration surface: authenticated sources submit normalized events and
incidents, and the product owns evidence, investigations, proposals, execution
claims, verification, rollback, and audit records.

The SentinelZone connector is optional compatibility support. It is a
read-only, administrator-configured adapter under `app/connectors/sentinelzone/`
and is disabled until an explicit upstream URL, token, tenant, and contract
are supplied. It is never used by the standalone composition path. The adapter
does not import another application's ORM or database and never writes back to
SentinelZone.

## Generic source contract

Implement a connector under `app/connectors/<name>/` with a bounded transport,
explicit contract schema, tenant checks, stable source and external IDs,
duplicate-safe normalization, and provenance mapping. A connector must remain
`NOT IMPLEMENTED` or `UNVERIFIED` until a real vendor contract is tested.

The product-owned HTTP endpoints are documented in [API.md](../API.md):

- `POST /v1/ingest/events`
- `POST /v1/ingest/incidents`
- `PUT /v1/assets/{asset_id}`

Every request is authenticated and tenant-scoped. The server validates the
source identity, data mode (`REAL`, `TEST`, `REPLAY`, or `UNKNOWN`), UTC
timestamps, bounded payloads, and stable IDs. A duplicate with the same
content is idempotent; a conflicting payload is rejected and audited.

## SentinelZone compatibility

See [the SentinelZone adapter guide](integrations/sentinelzone.md) for the
optional read-only mapping contract and explicit verification status. Historical
v0.29.x integration notes are retained in the supplied provenance materials;
they do not define standalone defaults and must not be interpreted as a
required dashboard, port, tenant, or private network.
