# Optional SentinelZone adapter

The SentinelZone adapter is optional and is not required for startup, ingestion, AI investigation, or dry-run SOAR. It performs authenticated read-only GET requests through a narrow mapper and preserves upstream provenance. It never writes back to SentinelZone Core and never reads its database.

Live compatibility is `UNVERIFIED` in this release because no current SentinelZone deployment was available. Contract mocks cover incident context, timeline membership, alert existence, tenant scope, pagination, and asset lookup. Before enabling it, configure `CORE_MODE=real`, an explicit tenant, a read-only token, HTTPS, and a verified CA; run the supplied contract preflight against a disposable/read-only scope. Missing or incomplete upstream data fails closed and remains UNKNOWN.

The importer copies verified context into the product-owned evidence store. It does not make imported REAL data eligible for live containment automatically; policy and executor gates still apply.
