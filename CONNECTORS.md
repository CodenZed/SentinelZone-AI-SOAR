# Connectors

Connectors implement a narrow boundary: authenticated input, bounded response, explicit source identity, normalized product contracts, tenant scope, provenance, and safe failure.

`generic_rest` and `webhook` validate `EventBatch` JSON and are implemented. `wazuh` and `splunk` expose skeleton interfaces and return `NOT IMPLEMENTED`; no vendor endpoint or field mapping is guessed. `sentinelzone` is optional read-only REST and is documented in [docs/integrations/sentinelzone.md](docs/integrations/sentinelzone.md). Its live contract is `UNVERIFIED` until an organization runs an authenticated preflight against its own deployment.

The product-owned ingestion endpoints are the portable integration surface. Vendor adapters should translate into them or call the repository service. Every event retains `(source_id, external_id)`, content hash, mode, and provenance. Duplicate identical submissions are safe; conflicting content returns 409.
