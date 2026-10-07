# Integration model

SentinelZone AI/SOAR can be used without any upstream service. Its API is the integration surface: authenticated sources submit normalized events/incidents and the product owns evidence, investigations, proposals, and audit.

The optional SentinelZone adapter is one connector among several. It performs read-only authenticated REST and maps a verified response into the repository. There is no Core database URL, shared ORM, dashboard dependency, fixed upstream port, fixed tenant, or write-back API in the standalone path.

For external systems, implement a connector under `app/connectors/<name>/` with a bounded transport, explicit contract schema, provenance mapping, tenant checks, duplicate-safe external identity, and mocked tests. Mark it NOT IMPLEMENTED or UNVERIFIED until a real contract is tested.
